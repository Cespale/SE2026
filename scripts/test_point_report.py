#!/usr/bin/env python3
"""Count executable assertions without changing the UC01-UC08 test cases."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_TEST_DIR = ROOT / "backend" / "tests"
E2E_SPEC = ROOT / "e2e" / "streamhub.spec.ts"

EXPECTED_BACKEND_TESTS = {
    "test_audit_status_allows_final_decisions_only",
    "test_creator_create_then_end_own_room",
    "test_normal_user_cannot_end_live_room",
    "test_normal_user_cannot_create_live_room",
    "test_user_can_send_live_websocket_message",
    "test_live_websocket_disconnect_during_join_is_not_unhandled",
    "test_avatar_upload_writes_to_object_storage",
    "test_cover_upload_writes_to_object_storage",
    "test_video_upload_writes_to_object_storage",
    "test_media_route_supports_video_byte_ranges",
    "test_upload_stream_creates_bucket_and_preserves_content_metadata",
    "test_from_env_requires_minio_secret",
    "test_legacy_migration_copies_files_without_deleting_originals",
    "test_object_name_from_url_accepts_only_media_paths",
    "test_object_name_from_url_rejects_non_media_or_traversal_paths",
    "test_parse_range_header_supports_video_seeking",
    "test_parse_range_header_rejects_invalid_or_multiple_ranges",
    "test_password_hash_and_verify",
    "test_token_can_be_parsed_back_to_user_id",
    "test_invalid_token_returns_401",
    "test_user_can_search_get_detail_and_playable_video_data",
    "test_user_can_like_favorite_comment_and_send_danmaku",
    "test_creator_only_reads_own_videos",
    "test_creator_submit_then_admin_approve_video",
    "test_normal_user_cannot_submit_video",
    "test_admin_can_reject_submitted_video",
    "test_normal_user_cannot_audit_video",
    "test_admin_cannot_return_submitted_video_to_pending",
    "test_admin_cannot_audit_nonexistent_video",
}

EXPECTED_E2E_TESTS = {
    "E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕",
    "E2E-TC03-05：创作者投稿，管理员审核，创作者查看结果",
    "E2E-TC06-08：创建直播、观众发弹幕、接口结束直播",
}

USE_CASE_BY_BACKEND_TEST = {
    "test_audit_status_allows_final_decisions_only": "UC04",
    "test_creator_create_then_end_own_room": "UC06/UC08",
    "test_normal_user_cannot_end_live_room": "UC08",
    "test_normal_user_cannot_create_live_room": "UC06",
    "test_user_can_send_live_websocket_message": "UC07",
    "test_live_websocket_disconnect_during_join_is_not_unhandled": "UC07",
    "test_avatar_upload_writes_to_object_storage": "UC03",
    "test_cover_upload_writes_to_object_storage": "UC03",
    "test_video_upload_writes_to_object_storage": "UC03",
    "test_media_route_supports_video_byte_ranges": "UC01",
    "test_upload_stream_creates_bucket_and_preserves_content_metadata": "UC03",
    "test_from_env_requires_minio_secret": "UC03",
    "test_legacy_migration_copies_files_without_deleting_originals": "UC03",
    "test_object_name_from_url_accepts_only_media_paths": "UC01/UC03",
    "test_object_name_from_url_rejects_non_media_or_traversal_paths": "UC03",
    "test_parse_range_header_supports_video_seeking": "UC01",
    "test_parse_range_header_rejects_invalid_or_multiple_ranges": "UC01",
    "test_password_hash_and_verify": "UC01-UC08",
    "test_token_can_be_parsed_back_to_user_id": "UC01-UC08",
    "test_invalid_token_returns_401": "UC01-UC08",
    "test_user_can_search_get_detail_and_playable_video_data": "UC01",
    "test_user_can_like_favorite_comment_and_send_danmaku": "UC02",
    "test_creator_only_reads_own_videos": "UC05",
    "test_creator_submit_then_admin_approve_video": "UC03/UC04/UC05",
    "test_normal_user_cannot_submit_video": "UC03",
    "test_admin_can_reject_submitted_video": "UC04",
    "test_normal_user_cannot_audit_video": "UC04",
    "test_admin_cannot_return_submitted_video_to_pending": "UC04",
    "test_admin_cannot_audit_nonexistent_video": "UC04",
}

USE_CASE_BY_E2E_CONTEXT = {
    "login": "UC01-UC08",
    "clearLogin": "UC03/UC04/UC05",
    "E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕": "UC01/UC02",
    "E2E-TC03-05：创作者投稿，管理员审核，创作者查看结果": "UC03/UC04/UC05",
    "E2E-TC06-08：创建直播、观众发弹幕、接口结束直播": "UC06/UC07/UC08",
}

FAILURE_NAME_PARTS = (
    "cannot",
    "invalid",
    "rejects",
    "nonexistent",
    "disconnect",
)


@dataclass(frozen=True)
class Point:
    layer: str
    use_cases: str
    branch: str
    file: str
    line: int
    test_case: str
    expression: str


def _compact(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return ""


def _is_failure_point(test_name: str, expression: str, is_raises: bool) -> bool:
    lowered = f"{test_name} {expression}".lower()
    return (
        is_raises
        or any(part in lowered for part in FAILURE_NAME_PARTS)
        or any(code in expression for code in ("== 401", "== 403", "== 404", "== 422"))
        or " is false" in lowered
    )


def collect_backend_points() -> tuple[list[Point], set[str]]:
    points: list[Point] = []
    tests: set[str] = set()
    for path in sorted(BACKEND_TEST_DIR.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        def enclosing_test(node: ast.AST) -> str:
            current: ast.AST | None = node
            while current is not None:
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return current.name
                current = parents.get(current)
            return "<module>"

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                tests.add(node.name)

            is_raises = False
            expression = ""
            if isinstance(node, ast.Assert):
                expression = ast.get_source_segment(source, node.test) or "assert"
            elif isinstance(node, ast.With) and any(
                _call_name(item.context_expr) == "raises" for item in node.items
            ):
                is_raises = True
                expression = ast.get_source_segment(source, node.items[0].context_expr) or "pytest.raises"
            else:
                continue

            test_name = enclosing_test(node)
            if not test_name.startswith("test_"):
                continue
            layer = "单元测试" if path.stem.endswith("_unit") else "集成/API测试"
            points.append(
                Point(
                    layer=layer,
                    use_cases=USE_CASE_BY_BACKEND_TEST[test_name],
                    branch=(
                        "失败/异常分支"
                        if _is_failure_point(test_name, expression, is_raises)
                        else "成功/正常分支"
                    ),
                    file=path.relative_to(ROOT).as_posix(),
                    line=node.lineno,
                    test_case=test_name,
                    expression=_compact(expression),
                )
            )
    return points, tests


def collect_e2e_points() -> tuple[list[Point], set[str]]:
    source = E2E_SPEC.read_text(encoding="utf-8")
    title_matches = list(
        re.finditer(r"""test\(\s*['"](?P<title>[^'"]+)['"]""", source)
    )
    function_matches = list(
        re.finditer(r"async function\s+(?P<name>\w+)\s*\(", source)
    )
    contexts = sorted(
        [(match.start(), match.group("title")) for match in title_matches]
        + [(match.start(), match.group("name")) for match in function_matches]
    )
    tests = {match.group("title") for match in title_matches}
    points: list[Point] = []
    source_lines = source.splitlines()
    for match in re.finditer(r"\bexpect\s*\(", source):
        context = max(
            (item for item in contexts if item[0] < match.start()),
            default=(0, "<module>"),
        )[1]
        line = source.count("\n", 0, match.start()) + 1
        points.append(
            Point(
                layer="系统/E2E测试",
                use_cases=USE_CASE_BY_E2E_CONTEXT.get(context, "UC01-UC08"),
                branch="成功/正常分支",
                file=E2E_SPEC.relative_to(ROOT).as_posix(),
                line=line,
                test_case=context,
                expression=_compact(source_lines[line - 1].strip()),
            )
        )
    return points, tests


def render_report(points: list[Point], backend_tests: set[str], e2e_tests: set[str]) -> str:
    layer_counts = Counter(point.layer for point in points)
    branch_counts = Counter(point.branch for point in points)
    lines = [
        "# UC01–UC08 测试点清单",
        "",
        "> 测试用例保持不变：后端测试函数 29 个（pytest 实际收集 38 项），"
        "前端 Playwright 场景 3 个。测试点按可执行 assert、pytest.raises、"
        "expect 逐项统计。",
        "",
        "## 汇总",
        "",
        "| 项目 | 数量 |",
        "| --- | ---: |",
        f"| 后端测试函数 | {len(backend_tests)} |",
        f"| 前端 E2E 场景 | {len(e2e_tests)} |",
        f"| 单元测试点 | {layer_counts['单元测试']} |",
        f"| 集成/API 测试点 | {layer_counts['集成/API测试']} |",
        f"| 系统/E2E 测试点 | {layer_counts['系统/E2E测试']} |",
        f"| 成功/正常分支测试点 | {branch_counts['成功/正常分支']} |",
        f"| 失败/异常分支测试点 | {branch_counts['失败/异常分支']} |",
        f"| **测试点总计** | **{len(points)}** |",
        "",
        "## 明细",
        "",
        "| 测试点 | 层级 | 关联用例 | 分支 | 测试函数/场景 | 代码位置 | 检查内容 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    counters: Counter[str] = Counter()
    prefixes = {
        "单元测试": "UNIT",
        "集成/API测试": "API",
        "系统/E2E测试": "E2E",
    }
    for point in points:
        prefix = prefixes[point.layer]
        counters[prefix] += 1
        point_id = f"TP-{prefix}-{counters[prefix]:03d}"
        lines.append(
            f"| {point_id} | {point.layer} | {point.use_cases} | {point.branch} | "
            f"{point.test_case} | {point.file}:{point.line} | {point.expression} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-total", type=int, default=200)
    parser.add_argument("--min-e2e", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    backend_points, backend_tests = collect_backend_points()
    e2e_points, e2e_tests = collect_e2e_points()
    points = backend_points + e2e_points

    errors = []
    if backend_tests != EXPECTED_BACKEND_TESTS:
        errors.append(
            "后端测试用例发生变化："
            f"新增={sorted(backend_tests - EXPECTED_BACKEND_TESTS)}，"
            f"缺少={sorted(EXPECTED_BACKEND_TESTS - backend_tests)}"
        )
    if e2e_tests != EXPECTED_E2E_TESTS:
        errors.append(
            "E2E 测试用例发生变化："
            f"新增={sorted(e2e_tests - EXPECTED_E2E_TESTS)}，"
            f"缺少={sorted(EXPECTED_E2E_TESTS - e2e_tests)}"
        )
    if len(points) < args.min_total:
        errors.append(f"测试点不足：当前 {len(points)}，要求至少 {args.min_total}")
    if len(e2e_points) < args.min_e2e:
        errors.append(
            f"前端 E2E 测试点不足：当前 {len(e2e_points)}，"
            f"要求至少 {args.min_e2e}"
        )
    if not any(point.branch == "失败/异常分支" for point in points):
        errors.append("测试点中没有失败/异常分支")

    report = render_report(points, backend_tests, e2e_tests)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")

    counts = Counter(point.layer for point in points)
    failure_count = sum(point.branch == "失败/异常分支" for point in points)
    print(
        f"TEST_CASES_BACKEND={len(backend_tests)} "
        f"TEST_CASES_E2E={len(e2e_tests)} "
        f"POINTS_UNIT={counts['单元测试']} "
        f"POINTS_API={counts['集成/API测试']} "
        f"POINTS_E2E={counts['系统/E2E测试']} "
        f"POINTS_FAILURE={failure_count} "
        f"POINTS_TOTAL={len(points)}"
    )
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())

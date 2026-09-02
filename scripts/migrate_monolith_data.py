import os
import sys

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.dialects.postgresql import insert


TABLE_MAP = {
    "users": "user_service",
    "follows": "user_service",
    "conversations": "user_service",
    "messages": "user_service",
    "notifications": "user_service",
    "categories": "content_service",
    "videos": "content_service",
    "comments": "social_service",
    "comment_mentions": "social_service",
    "video_likes": "social_service",
    "danmaku": "social_service",
    "live_rooms": "social_service",
    "reports": "social_service",
    "sensitive_words": "social_service",
}

IDENTITY_TABLES = {
    "categories": "content_service",
    "sensitive_words": "social_service",
}


def grouped_counts(source_engine, source_inspector, table_name: str) -> dict:
    if not source_inspector.has_table(table_name, schema="public"):
        return {}
    table = Table(
        table_name,
        MetaData(),
        schema="public",
        autoload_with=source_engine,
    )
    with source_engine.connect() as connection:
        rows = connection.execute(
            select(table.c.video_id, func.count()).group_by(table.c.video_id)
        ).all()
    return {row[0]: int(row[1]) for row in rows}


def seed_interaction_baselines(
    source_engine,
    destination_engine,
    source_inspector,
) -> None:
    if not source_inspector.has_table("videos", schema="public"):
        return
    videos = Table(
        "videos",
        MetaData(),
        schema="public",
        autoload_with=source_engine,
    )
    target = Table(
        "video_interaction_baselines",
        MetaData(),
        schema="social_service",
        autoload_with=destination_engine,
    )
    like_details = grouped_counts(source_engine, source_inspector, "video_likes")
    comment_details = grouped_counts(source_engine, source_inspector, "comments")
    favorite_details = grouped_counts(
        source_engine, source_inspector, "video_favorites"
    )
    with source_engine.connect() as connection:
        source_rows = connection.execute(
            select(
                videos.c.id,
                videos.c.like_count,
                videos.c.comment_count,
                videos.c.favorite_count,
            )
        ).all()
    baselines = [
        {
            "video_id": row.id,
            "like_count": max(int(row.like_count or 0) - like_details.get(row.id, 0), 0),
            "comment_count": max(
                int(row.comment_count or 0) - comment_details.get(row.id, 0), 0
            ),
            "favorite_count": max(
                int(row.favorite_count or 0) - favorite_details.get(row.id, 0), 0
            ),
        }
        for row in source_rows
    ]
    with destination_engine.begin() as connection:
        if baselines:
            connection.execute(
                insert(target).values(baselines).on_conflict_do_nothing()
            )
    print(f"video_interaction_baselines: source={len(source_rows)} seeded={len(baselines)}")


def copy_rows(source_url: str, destination_url: str) -> None:
    source_engine = create_engine(source_url, pool_pre_ping=True)
    destination_engine = create_engine(destination_url, pool_pre_ping=True)
    source_inspector = inspect(source_engine)

    try:
        for table_name, target_schema in TABLE_MAP.items():
            if not source_inspector.has_table(table_name, schema="public"):
                print(f"{table_name}: source=missing skipped=true")
                continue

            source_table = Table(
                table_name,
                MetaData(),
                schema="public",
                autoload_with=source_engine,
            )
            target_table = Table(
                table_name,
                MetaData(),
                schema=target_schema,
                autoload_with=destination_engine,
            )
            column_names = [
                column.name
                for column in target_table.columns
                if column.name in source_table.columns
            ]

            with source_engine.connect() as source_connection:
                rows = source_connection.execute(
                    select(*(source_table.c[name] for name in column_names))
                ).mappings().all()
                source_count = source_connection.scalar(
                    select(func.count()).select_from(source_table)
                )

            with destination_engine.begin() as destination_connection:
                if rows:
                    statement = insert(target_table).values([dict(row) for row in rows])
                    destination_connection.execute(statement.on_conflict_do_nothing())
                target_count = destination_connection.scalar(
                    select(func.count()).select_from(target_table)
                )

            print(
                f"{table_name}: source={source_count} target={target_count}"
            )
            if target_count is None or source_count is None or target_count < source_count:
                raise RuntimeError(f"row count mismatch for {table_name}")

        seed_interaction_baselines(
            source_engine,
            destination_engine,
            source_inspector,
        )

        with destination_engine.begin() as destination_connection:
            for table_name, target_schema in IDENTITY_TABLES.items():
                destination_connection.execute(
                    text(
                        "SELECT setval("
                        "pg_get_serial_sequence(:qualified_table, 'id'), "
                        f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
                        f"FROM {target_schema}.{table_name}"
                    ),
                    {"qualified_table": f"{target_schema}.{table_name}"},
                )
    finally:
        source_engine.dispose()
        destination_engine.dispose()


def main() -> int:
    source_url = os.getenv("SOURCE_DATABASE_URL")
    destination_url = os.getenv("DESTINATION_DATABASE_URL")
    if not source_url or not destination_url:
        print("DATA_MIGRATION=FAIL type=MissingDatabaseUrl", file=sys.stderr)
        return 2

    try:
        copy_rows(source_url, destination_url)
    except Exception as exc:
        print(f"DATA_MIGRATION=FAIL type={type(exc).__name__}", file=sys.stderr)
        return 1

    print("DATA_MIGRATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

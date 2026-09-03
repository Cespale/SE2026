from app.database import SessionLocal
from app.models import Comment, Report, SensitiveWord


def test_reports_and_sensitive_words_admin_flow(client, auth_headers, ids):
    report = client.post(
        "/api/reports",
        headers=auth_headers("viewer"),
        json={"target_type": 0, "target_id": ids["video"], "reason": "spam"},
    )
    assert report.status_code == 200
    report_id = report.json()["id"]
    assert client.get(
        "/api/admin/reports", headers=auth_headers("admin")
    ).status_code == 200
    assert client.patch(
        f"/api/admin/reports/{report_id}/handle",
        headers=auth_headers("admin"),
    ).status_code == 200

    added = client.post(
        "/api/admin/sensitive-words",
        headers=auth_headers("admin"),
        json={"word": "blocked"},
    )
    assert added.status_code == 200
    word_id = added.json()["id"]
    words = client.get(
        "/api/admin/sensitive-words", headers=auth_headers("admin")
    )
    assert words.status_code == 200
    # 契约：列表必须返回 {"items": [...]}，前端按 data.items 读取
    items = words.json()["items"]
    assert any(item["word"] == "blocked" for item in items)
    assert client.delete(
        f"/api/admin/sensitive-words/{word_id}", headers=auth_headers("admin")
    ).status_code == 200


def test_sensitive_words_are_masked_not_rejected(client, auth_headers, ids):
    # 敏感词应被替换成等长 *号而不是 400 拒绝发送
    client.post(
        "/api/admin/sensitive-words",
        headers=auth_headers("admin"),
        json={"word": "blocked"},
    )
    comment = client.post(
        f"/api/videos/{ids['video']}/comments",
        headers=auth_headers("viewer"),
        json={"content": "this is blocked now", "parentId": "0"},
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["content"] == "this is ******* now"

    danmaku = client.post(
        f"/api/videos/{ids['video']}/danmaku",
        headers=auth_headers("viewer"),
        json={"content": "blocked!!", "videoTime": 3},
    )
    assert danmaku.status_code == 200, danmaku.text
    assert danmaku.json()["content"] == "*******!!"


def test_admin_live_and_user_likes_routes(client, auth_headers, ids):
    room = client.post(
        "/api/live/rooms",
        headers=auth_headers("creator"),
        json={"title": "Moderated", "categoryId": "1"},
    ).json()
    assert client.get(
        "/api/admin/live-rooms", headers=auth_headers("admin")
    ).status_code == 200
    assert client.post(
        f"/api/admin/live-rooms/{room['id']}/warn",
        headers=auth_headers("admin"),
        json={"reason": "warning"},
    ).status_code == 200
    assert client.post(
        f"/api/admin/live-rooms/{room['id']}/close",
        headers=auth_headers("admin"),
        json={"reason": "close"},
    ).status_code == 200

    client.post(
        f"/api/videos/{ids['video']}/like", headers=auth_headers("viewer")
    )
    likes = client.get(
        f"/api/users/{ids['viewer']}/likes", headers=auth_headers("viewer")
    )
    assert likes.status_code == 200
    assert likes.json()["total"] == 1

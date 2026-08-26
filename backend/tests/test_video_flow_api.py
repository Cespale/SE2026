def login_headers(client, account, password):
    response = client.post(
        "/api/auth/login",
        json={"account": account, "password": password},
    )

    assert response.status_code == 200

    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_creator_submit_then_admin_approve_video(client):
    creator_headers = login_headers(client, "creator", "creator123")
    admin_headers = login_headers(client, "admin", "admin123")

    create_response = client.post(
        "/api/videos",
        headers=creator_headers,
        json={
            "title": "pytest 投稿视频",
            "description": "用于 API 集成测试",
            "tags": ["pytest", "测试"],
            "coverUrl": "",
            "videoUrl": "/demo-videos/video1.mp4",
            "duration": 60,
            "categoryId": "1",
        },
    )

    assert create_response.status_code == 200

    created_video = create_response.json()
    video_id = created_video["id"]

    assert created_video["title"] == "pytest 投稿视频"
    assert created_video["auditStatus"] == 0

    pending_response = client.get(
        "/api/admin/videos/pending",
        headers=admin_headers,
    )

    assert pending_response.status_code == 200
    pending_ids = [video["id"] for video in pending_response.json()["items"]]
    assert video_id in pending_ids

    audit_response = client.patch(
        f"/api/admin/videos/{video_id}/audit",
        headers=admin_headers,
        json={"auditStatus": 1},
    )

    assert audit_response.status_code == 200
    assert audit_response.json()["auditStatus"] == 1

    creator_videos_response = client.get(
        "/api/creator/videos",
        headers=creator_headers,
    )

    assert creator_videos_response.status_code == 200

    creator_video = next(
        video
        for video in creator_videos_response.json()["items"]
        if video["id"] == video_id
    )

    assert creator_video["auditStatus"] == 1


def test_normal_user_cannot_submit_video(client):
    user_headers = login_headers(client, "user", "user123")

    response = client.post(
        "/api/videos",
        headers=user_headers,
        json={
            "title": "普通用户不能投稿",
            "categoryId": "1",
        },
    )

    assert response.status_code == 403


def test_admin_can_reject_submitted_video(client):
    creator_headers = login_headers(client, "creator", "creator123")
    admin_headers = login_headers(client, "admin", "admin123")

    create_response = client.post(
        "/api/videos",
        headers=creator_headers,
        json={
            "title": "pytest 驳回投稿",
            "categoryId": "1",
        },
    )

    assert create_response.status_code == 200

    response = client.patch(
        f"/api/admin/videos/{create_response.json()['id']}/audit",
        headers=admin_headers,
        json={"auditStatus": 2},
    )

    assert response.status_code == 200
    assert response.json()["auditStatus"] == 2


def test_normal_user_cannot_audit_video(client):
    creator_headers = login_headers(client, "creator", "creator123")
    user_headers = login_headers(client, "user", "user123")

    create_response = client.post(
        "/api/videos",
        headers=creator_headers,
        json={
            "title": "pytest 无权审核",
            "categoryId": "1",
        },
    )

    assert create_response.status_code == 200

    response = client.patch(
        f"/api/admin/videos/{create_response.json()['id']}/audit",
        headers=user_headers,
        json={"auditStatus": 1},
    )

    assert response.status_code == 403


def test_admin_cannot_return_submitted_video_to_pending(client):
    creator_headers = login_headers(client, "creator", "creator123")
    admin_headers = login_headers(client, "admin", "admin123")
    create_response = client.post(
        "/api/videos",
        headers=creator_headers,
        json={"title": "pytest 非法审核状态", "categoryId": "1"},
    )

    assert create_response.status_code == 200
    video_id = create_response.json()["id"]

    response = client.patch(
        f"/api/admin/videos/{video_id}/audit",
        headers=admin_headers,
        json={"auditStatus": 0},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "auditStatus"]
    assert response.json()["detail"][0]["type"] == "literal_error"

    pending_response = client.get("/api/admin/videos/pending", headers=admin_headers)
    assert pending_response.status_code == 200
    pending_video = next(
        video for video in pending_response.json()["items"] if video["id"] == video_id
    )
    assert pending_video["auditStatus"] == 0


def test_admin_cannot_audit_nonexistent_video(client):
    admin_headers = login_headers(client, "admin", "admin123")

    response = client.patch(
        "/api/admin/videos/00000000-0000-0000-0000-000000000001/audit",
        headers=admin_headers,
        json={"auditStatus": 1},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "视频不存在"}

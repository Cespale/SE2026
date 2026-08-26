def login(client, account, password):
    response = client.post(
        "/api/auth/login",
        json={"account": account, "password": password},
    )

    assert response.status_code == 200

    data = response.json()
    return data["user"], {"Authorization": f"Bearer {data['token']}"}


def first_video(client):
    response = client.get("/api/videos")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0

    # 种子数据至少会写入 6 条外网可播放视频；CI 里 public/demo-videos 未提交，
    # 所以这里直接取第一条，不强制要求本地 /demo-videos/ 视频。
    return items[0]


def test_user_can_search_get_detail_and_playable_video_data(client):
    video = first_video(client)

    detail_response = client.get(f"/api/videos/{video['id']}")

    assert detail_response.status_code == 200

    detail = detail_response.json()

    assert detail["id"] == video["id"]
    assert detail["videoUrl"]  # 有可播放的视频地址（本地 /demo-videos/ 或外网 http）
    assert detail["viewCount"] == video["viewCount"] + 1

    empty_search = client.get(
        "/api/videos?keyword=this-video-must-not-exist-pytest"
    )

    assert empty_search.status_code == 200
    assert empty_search.json()["items"] == []


def test_user_can_like_favorite_comment_and_send_danmaku(client):
    _, user_headers = login(client, "user", "user123")
    video = first_video(client)

    like_response = client.post(
        f"/api/videos/{video['id']}/like",
        headers=user_headers,
    )

    assert like_response.status_code == 200
    assert like_response.json()["likeCount"] == video["likeCount"] + 1

    favorite_response = client.post(
        f"/api/videos/{video['id']}/favorite",
        headers=user_headers,
    )

    assert favorite_response.status_code == 200
    assert favorite_response.json()["favoriteCount"] == video["favoriteCount"] + 1

    comment_response = client.post(
        f"/api/videos/{video['id']}/comments",
        headers=user_headers,
        json={"content": "pytest 评论内容"},
    )

    assert comment_response.status_code == 200
    assert comment_response.json()["content"] == "pytest 评论内容"

    comments_response = client.get(
        f"/api/videos/{video['id']}/comments"
    )

    assert comments_response.status_code == 200
    assert "pytest 评论内容" in [
        item["content"] for item in comments_response.json()
    ]

    danmaku_response = client.post(
        f"/api/videos/{video['id']}/danmaku",
        headers=user_headers,
        json={
            "content": "pytest 弹幕内容",
            "color": "#FFFFFF",
            "position": 0,
            "videoTime": 3,
        },
    )

    assert danmaku_response.status_code == 200
    assert danmaku_response.json()["content"] == "pytest 弹幕内容"


def test_creator_only_reads_own_videos(client):
    creator, creator_headers = login(client, "creator", "creator123")
    _, user_headers = login(client, "user", "user123")

    creator_response = client.get(
        "/api/creator/videos",
        headers=creator_headers,
    )

    assert creator_response.status_code == 200

    for video in creator_response.json()["items"]:
        assert video["uploaderId"] == creator["id"]

    user_response = client.get(
        "/api/creator/videos",
        headers=user_headers,
    )

    assert user_response.status_code == 403
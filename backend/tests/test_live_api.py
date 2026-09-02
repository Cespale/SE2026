import asyncio

from app.main import live_hub, live_ws


def login_headers(client, account, password):
    response = client.post(
        "/api/auth/login",
        json={"account": account, "password": password},
    )

    assert response.status_code == 200

    token = response.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


def create_live_room(client, headers):
    response = client.post(
        "/api/live/rooms",
        headers=headers,
        json={
            "title": "pytest 直播间",
            "categoryId": "10",
            "cover": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == 1

    return response.json()


def test_creator_create_then_end_own_room(client):
    _, creator_headers = login_headers(client, "creator", "creator123")

    room = create_live_room(client, creator_headers)
    room_id = room["id"]

    assert room["title"] == "pytest 直播间"
    assert room["categoryId"] == "10"
    assert room["status"] == 1
    assert room["anchorId"]
    assert room["streamKey"]
    assert room["pushUrl"].startswith("rtmp://")
    assert room["pullUrl"].endswith(".flv")
    assert room["onlineCount"] == 0
    assert room["cover"]

    room_list = client.get("/api/live/rooms")

    assert room_list.status_code == 200
    assert isinstance(room_list.json()["items"], list)
    assert room_id in [item["id"] for item in room_list.json()["items"]]

    end_response = client.post(
        f"/api/live/rooms/{room_id}/end",
        headers=creator_headers,
    )

    assert end_response.status_code == 200
    assert end_response.json()["ok"] is True

    active_rooms = client.get("/api/live/rooms")

    assert active_rooms.status_code == 200
    assert room_id not in [item["id"] for item in active_rooms.json()["items"]]


def test_normal_user_cannot_end_live_room(client):
    _, creator_headers = login_headers(client, "creator", "creator123")
    _, user_headers = login_headers(client, "user", "user123")

    room = create_live_room(client, creator_headers)

    response = client.post(
        f"/api/live/rooms/{room['id']}/end",
        headers=user_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "需要创作者权限"


def test_normal_user_cannot_create_live_room(client):
    _, user_headers = login_headers(client, "user", "user123")

    response = client.post(
        "/api/live/rooms",
        headers=user_headers,
        json={
            "title": "普通用户不能开播",
            "categoryId": "10",
            "cover": "",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "需要创作者权限"


def test_user_can_send_live_websocket_message(client):
    user_token, user_headers = login_headers(client, "user", "user123")
    _, creator_headers = login_headers(client, "creator", "creator123")

    room = create_live_room(client, creator_headers)

    with client.websocket_connect(
        f"/ws/live/{room['id']}?token={user_token}"
    ) as websocket:
        initial_messages = [
            websocket.receive_json(),
            websocket.receive_json(),
            websocket.receive_json(),
        ]

        assert [message["type"] for message in initial_messages] == [
            "online",
            "join_ack",
            "system",
        ]

        assert initial_messages[0]["count"] >= 1
        assert initial_messages[1]["onlineCount"] >= 1
        assert initial_messages[2]["content"].endswith("进入直播间")
        assert "timestamp" in initial_messages[2]
        websocket.send_json(
            {
                "type": "danmaku",
                "content": "pytest 直播消息",
                "color": "#FFFFFF",
                "position": 0,
            }
        )

        message = websocket.receive_json()

        assert message["type"] == "danmaku"
        assert message["content"] == "pytest 直播消息"
        assert message["color"] == "#FFFFFF"
        assert message["position"] == 0
        assert message["username"]
        assert message["userId"]
        assert len(message["id"]) == 16
        assert "timestamp" in message


def test_live_websocket_disconnect_during_join_is_not_unhandled():
    class ClosingWebSocket:
        async def accept(self):
            return None

        async def send_json(self, _payload):
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    room_id = "closing-websocket-test"
    live_hub.rooms.pop(room_id, None)

    asyncio.run(live_ws(ClosingWebSocket(), room_id))

    assert isinstance(live_hub.rooms, dict)
    assert room_id not in live_hub.rooms or not live_hub.rooms[room_id]

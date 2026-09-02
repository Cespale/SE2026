from app.database import SessionLocal
from app.models import LiveRoom
from uuid import UUID


def test_live_room_create_list_get_end_and_websocket(client, auth_headers):
    created = client.post(
        "/api/live/rooms",
        headers=auth_headers("creator"),
        json={"title": "Live", "categoryId": "1", "cover": "", "description": "demo"},
    )
    assert created.status_code == 200
    assert created.json()["pushUrl"].startswith("rtmp://localhost:1936/live/")
    assert created.json()["pullUrl"].startswith("http://localhost:8081/live/")
    room_id = created.json()["id"]
    listing = client.get("/api/live/rooms?category_id=1")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == room_id
    duplicate = client.post(
        "/api/live/rooms",
        headers=auth_headers("creator"),
        json={"title": "Duplicate", "categoryId": "1"},
    )
    assert duplicate.status_code == 400
    assert client.get(f"/api/live/rooms/{room_id}").status_code == 200

    with client.websocket_connect(f"/ws/live/{room_id}") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()
        assert {first["type"], second["type"]} == {"online", "join_ack"}
        websocket.send_json({"type": "heartbeat"})
        assert websocket.receive_json()["type"] in {"system", "online"}

    ended = client.post(
        f"/api/live/rooms/{room_id}/end", headers=auth_headers("creator")
    )
    assert ended.status_code == 200
    with SessionLocal() as db:
        assert db.get(LiveRoom, UUID(room_id)).status == 2


def test_creator_active_room_and_live_danmaku(client, auth_headers):
    created = client.post(
        "/api/live/rooms",
        headers=auth_headers("creator"),
        json={"title": "Live", "categoryId": "1"},
    ).json()
    assert client.get(
        "/api/creator/active-room", headers=auth_headers("creator")
    ).status_code == 200
    sent = client.post(
        f"/api/live/{created['id']}/danmaku",
        headers=auth_headers("viewer"),
        json={"content": "hi", "color": "#fff"},
    )
    assert sent.status_code == 200
    assert client.post(
        f"/api/live/rooms/{created['id']}/stop",
        headers=auth_headers("creator"),
    ).status_code == 200

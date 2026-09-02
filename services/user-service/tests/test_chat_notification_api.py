from app.database import SessionLocal
from app.main import get_or_create_conversation
from app.models import Notification, ProcessedEvent
from sqlalchemy.exc import IntegrityError


def test_internal_notification_is_atomic_and_idempotent(client, users):
    event = {
        "eventId": "11111111-1111-1111-1111-111111111111",
        "recipientId": users["alice"],
        "senderId": users["creator"],
        "notifType": 1,
        "targetType": 0,
        "targetId": "22222222-2222-2222-2222-222222222222",
        "content": "new comment",
    }
    first = client.post("/internal/notifications", json=event)
    second = client.post("/internal/notifications", json=event)
    assert first.status_code == second.status_code == 200
    assert second.json()["duplicate"] is True

    with SessionLocal() as db:
        assert db.query(Notification).count() == 1
        assert db.query(ProcessedEvent).count() == 1


def test_notification_list_counts_and_read_routes(client, auth_headers, users):
    client.post(
        "/internal/notifications",
        json={
            "eventId": "33333333-3333-3333-3333-333333333333",
            "recipientId": users["alice"],
            "senderId": users["creator"],
            "notifType": 1,
            "targetType": 0,
            "targetId": None,
            "content": "hello",
        },
    )
    headers = auth_headers("alice")
    rows = client.get("/api/notifications", headers=headers).json()
    assert len(rows) == 1
    assert client.get(
        "/api/notifications/unread-count", headers=headers
    ).json()["notification"] == 1
    assert client.post(
        f"/api/notifications/{rows[0]['id']}/read", headers=headers
    ).status_code == 200
    assert client.post(
        "/api/notifications/read-all", headers=headers
    ).status_code == 200


def test_chat_conversation_message_recall_read_and_websocket(
    client, auth_headers, users
):
    alice_headers = auth_headers("alice")
    conversation = client.post(
        "/api/chat/conversations",
        headers=alice_headers,
        json={"peerId": users["creator"]},
    )
    assert conversation.status_code == 200
    conversation_id = conversation.json()["id"]

    sent = client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        headers=alice_headers,
        json={"content": "hello", "messageType": 0},
    )
    assert sent.status_code == 200
    message_id = sent.json()["id"]
    assert len(client.get(
        f"/api/chat/conversations/{conversation_id}/messages",
        headers=alice_headers,
    ).json()) == 1
    assert len(client.get(
        "/api/chat/conversations", headers=alice_headers
    ).json()) == 1
    assert client.post(
        f"/api/chat/conversations/{conversation_id}/read",
        headers=auth_headers("creator"),
    ).status_code == 200
    assert client.post(
        f"/api/chat/messages/{message_id}/recall", headers=alice_headers
    ).status_code == 200

    token = alice_headers["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/chat?token={token}") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

    winner = object()
    query_results = [None, winner]

    class QueryStub:
        def filter(self, *_conditions):
            return self

        def first(self):
            return query_results.pop(0)

    class ConcurrentInsertSessionStub:
        def __init__(self):
            self.rolled_back = False

        def query(self, *_models):
            return QueryStub()

        def add(self, _row):
            return None

        def commit(self):
            raise IntegrityError("INSERT", {}, RuntimeError("duplicate pair"))

        def rollback(self):
            self.rolled_back = True

    concurrent_db = ConcurrentInsertSessionStub()
    resolved = get_or_create_conversation(
        concurrent_db,
        users["alice"],
        users["creator"],
    )
    assert resolved is winner
    assert concurrent_db.rolled_back is True

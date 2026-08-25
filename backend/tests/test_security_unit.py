import uuid

import pytest
from fastapi import HTTPException

from app.models import User
from app.security import create_token, hash_password, parse_token, verify_password


def test_password_hash_and_verify():
    password = "user123"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_token_can_be_parsed_back_to_user_id():
    user = User(
        id=uuid.uuid4(),
        account="test_user",
        password_hash="unused",
        nickname="测试用户",
    )

    token = create_token(user)

    assert parse_token(token) == str(user.id)


def test_invalid_token_returns_401():
    with pytest.raises(HTTPException) as error:
        parse_token("invalid-token")

    assert error.value.status_code == 401
import pytest
from datetime import datetime, timedelta
from jose import jwt
from services.auth_service.auth_handler import AuthHandler
from models.user import UserModel
from core.config import settings


def test_hash_and_verify_password(db):
    auth = AuthHandler(db)
    hashed = auth.get_password_hash("secret123")
    assert auth.verify_password("secret123", hashed) is True
    assert auth.verify_password("wrong", hashed) is False


def test_create_access_token(db):
    auth = AuthHandler(db)
    token = auth.create_access_token({"sub": 42})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "42"
    assert "exp" in payload


def test_decode_token_extracts_user_id(db):
    auth = AuthHandler(db)
    token = auth.create_access_token({"sub": 99})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "99"


def test_expired_token(db):
    auth = AuthHandler(db)
    expired_data = {"sub": 1, "exp": datetime.utcnow() - timedelta(minutes=5)}
    token = jwt.encode(expired_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    user = auth.get_current_user(token)
    assert user is None


def test_invalid_token(db):
    auth = AuthHandler(db)
    user = auth.get_current_user("invalid.token.here")
    assert user is None


def test_create_user(db, test_family):
    from core.schemas import UserCreate
    auth = AuthHandler(db)
    user = auth.create_user(UserCreate(
        email="new@example.com",
        full_name="New User",
        password="pass123",
    ))
    assert user.id is not None
    assert user.email == "new@example.com"


def test_authenticate_user(db, test_user):
    auth = AuthHandler(db)
    user = auth.authenticate_user("test@example.com", "password123")
    assert user is not None
    assert user.email == "test@example.com"


def test_authenticate_user_wrong_password(db, test_user):
    auth = AuthHandler(db)
    user = auth.authenticate_user("test@example.com", "wrong")
    assert user is None


def test_authenticate_user_nonexistent(db):
    auth = AuthHandler(db)
    user = auth.authenticate_user("nobody@example.com", "pass")
    assert user is None


def test_get_current_user_valid(db, test_user):
    auth = AuthHandler(db)
    token = auth.create_access_token({"sub": test_user.id})
    found = auth.get_current_user(token)
    assert found is not None
    assert found.id == test_user.id

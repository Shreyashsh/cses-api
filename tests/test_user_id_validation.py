# tests/test_user_id_validation.py
import pytest
from models.user_id import UserIdParam

def test_valid_user_id():
    """Valid user_id should be accepted."""
    user_id = UserIdParam(user_id="test_user-123")
    assert user_id.user_id == "test_user-123"

def test_invalid_user_id_special_chars():
    """user_id with special characters should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="test;user")

def test_invalid_user_id_path_traversal():
    """Path traversal attempts should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="../etc/passwd")

def test_empty_user_id():
    """Empty user_id should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="")

def test_too_long_user_id():
    """user_id over 64 chars should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="a" * 65)

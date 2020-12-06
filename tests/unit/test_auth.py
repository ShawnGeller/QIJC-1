import pytest

from app import db
from app.models import User, Paper

class TestUserModel():
    def test_password_hashing(self):
        u = User(username='susan')
        u.set_password('cat')
        assert not u.check_password('dog')
        assert u.check_password('cat')

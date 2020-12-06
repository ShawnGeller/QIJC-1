from datetime import datetime, timedelta
import unittest
from app import create_app, db
from app.models import User, Paper
from conftest import TestConfig

class TestUserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_submitter(self):
        u1 = User(username='austin')
        u2 = User(username='frank')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        self.assertEqual(u1.subs, [])
        self.assertEqual(u2.subs, [])
        p1 = Paper()
        p2 = Paper()
        db.session.add(p1, p2)
        db.session.commit()
        p1.subber = u1
        p2.subber = u2
        self.assertEqual(u1.subs[0], p1)
        self.assertEqual(u2.subs[0], p2)

    def test_volunteer(self):
        u1 = User(username='austin')
        u2 = User(username='frank')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        self.assertEqual(u1.vols, [])
        self.assertEqual(u2.vols, [])
        p1 = Paper()
        p2 = Paper()
        db.session.add(p1, p2)
        db.session.commit()
        p1.volunteer = u2
        p2.volunteer = u1
        self.assertEqual(u1.vols[0], p2)
        self.assertEqual(u2.vols[0], p1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

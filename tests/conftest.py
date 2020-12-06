import os
import tempfile
import pytest
import flask_login
from flask import url_for
from datetime import datetime, timedelta
from random import randint

from app import create_app, db
from app.models import User, Paper
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    WTF_CSRF_ENABLED = False
    BCRYPT_LOG_ROUNDS = 4

def fill_database():
    u0 = User(username='testadmin', admin=1, firstname='TestAdmin',
              lastname='Jenkins')
    u0.set_password('adminpw')
    u1 = User(username='testuser', firstname='John', lastname='Jimmies')
    u1.set_password('userpw')
    u2 = User(username='testretired', retired=1)
    u3 = User(username='testuser2', firstname='Lacy', lastname='Amil')
    u4 = User(username='testuser3', firstname='Sal', lastname='Andre')
    u5 = User(username='testuser4', firstname='Josh', lastname='Lago')
    u6 = User(username='testuser5', firstname='Holly', lastname='Ber')

    users = [u0, u1, u2, u3, u4, u5, u6]
    dates = [None, datetime.now().date(),
             (datetime.now() - timedelta(days=30)).date()]

    def create_papers(subs, vols, vots):
        papers = []
        params = ([[sub, vol, vot] for sub in subs
                      for vol in vols for vot in vots])
        i = 0
        for par in params:
            p = Paper(subber=par[0], volunteer=par[1], voted=par[2],
                      title=f'Paper {i}')
            papers.append(p)
            i += 1
        return papers

    papers = create_papers(users, users, dates)

    for paper in papers:
        paper.score_d = randint(2, len(users))
        paper.score_n = randint(0, paper.score_d)

    return users, papers
    
@pytest.fixture(scope='class')
def test_client():
    flask_app = create_app(TestConfig)
    with flask_app.test_client() as client:
        app_context = flask_app.app_context()
        app_context.push()
        db.create_all()
        users, papers = fill_database()
        for u in users:
            db.session.add(u)
        db.session.commit()
        for p in papers:
            db.session.add(p)
        db.session.commit()
        yield client
        db.drop_all()
    app_context.pop()

@pytest.fixture(scope='class')
def auth_client(test_client):
    test_client.post('/login', data=dict(
        username='testuser', password='userpw'),
                    follow_redirects=True)
    yield test_client
    test_client.get('/logout', follow_redirects=True)

@pytest.fixture(scope='function')
def logged_in_fxn(request, test_client):
    test_client.post('/login', data=dict(
        username='testuser', password='userpw'),
                    follow_redirects=True)
    yield test_client
    def logout():
        test_client.get('/logout', follow_redirects=True)
    request.addfinalizer(logout)
                                   

import pytest
from flask import url_for
from flask_login import current_user

from app import db
from app.models import User, Paper

@pytest.mark.usefixtures('test_client')
class TestFixtures():
    def test_login_fail(self, test_client):
        response = test_client.get('/', follow_redirects=True)
        assert b'Sign in' in response.data
        
    def test_login(self, logged_in_fxn):
        response = logged_in_fxn.get('/', follow_redirects=True)
        assert not b'Sign in' in response.data

    def test_login_fail_again(self, test_client):
        response = test_client.get('/', follow_redirects=True)
        assert b'Sign in' in response.data

@pytest.mark.usefixtures('auth_client')
class TestProfile():
    def test_access_profile(self, auth_client):
        '''
        Logged-in user is able to access their profile page.
        '''
        response = auth_client.get(url_for('main.user',
                                           username=(current_user
                                                     .username)))
        assert response.status_code == 200
        assert b'John Jimmies' in response.data

    def test_change_password(self, auth_client):
        '''
        Logged-in user is able to change their password.
        '''
        response = auth_client.post(url_for('main.user',
                                            username=current_user
                                            .username),
                                    data=dict(current_pass='userpw',
                                              new_pass='newuserpw',
                                              new_pass2='newuserpw'),
                                    follow_redirects=True)
        assert response.status_code == 200
        assert b'Password changed.' in response.data
        auth_client.get(url_for('auth.logout'))
        response = auth_client.post(url_for('auth.login'),
                             data=dict(username='testuser',
                                        password='newuserpw'),
                             follow_redirects=True)
        assert response.status_code == 200
        assert b'Quantum Information Journal' in response.data

    def test_change_email(self, auth_client):
        '''
        Logged-in user is able to change their email.
        '''
        new_email='testuser@email.com'
        response = auth_client.post(url_for('main.user',
                                            username=current_user
                                            .username),
                                    data=dict(new_email=new_email,
                                              new_email2=new_email),
                                    follow_redirects=True)
        assert response.status_code == 200
        assert b'Email updated.' in response.data
        assert bytes(new_email, 'utf-8') in response.data

    def test_subbed_papers_display(self, auth_client):
        '''
        Recent submitted papers display on user profile pages.
        '''
        for user in User.query.all():
            response = auth_client.get(url_for('main.user',
                                               username=user.username))
            papers = (Paper.query.filter(Paper.subber==user)
                      .order_by(Paper.timestamp.desc()))[:10]
            for paper in papers:
                assert bytes(paper.title, 'utf-8') in response.data

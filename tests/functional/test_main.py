import pytest
from flask import url_for
from datetime import datetime

from app.models import User, Paper
from app import db

@pytest.mark.usefixtures('auth_client')
class TestIndex():
    def test_loggedin(self, auth_client):
        '''
        Logged in user can access the index.
        '''
        response = auth_client.get('/')
        assert b'Quantum Information Journal Club' in response.data

    def test_only_display_nonretired_users(self, test_client):
        '''
        No retired users are displayed on the index scoreboard.
        '''
        response = test_client.get('/')
        usernames = (u.username for u in User.query.all()
                         if u.retired == 1)
        for username in usernames:
            assert not bytes(username, 'utf-8') in response.data

    def test_display_all_nonretired_users(self, test_client):
        '''
        All nonretired users are displayed on the index scoreboard.
        '''
        response = test_client.get('/')
        usernames = (u.username for u in User.query.all()
                         if u.retired == 0)
        for username in usernames:
            assert bytes(username, 'utf-8') in response.data
    
@pytest.mark.usefixtures('auth_client')
class TestSubmit():
    def test_submit_access(self, auth_client):
        '''
        Logged in user is able to access the submit page.
        '''
        response = auth_client.get(url_for('main.submit'))
        assert b'Submit' in response.data

    def test_subbed_nonvoted_papers_show(self, auth_client):
        '''
        All papers that have been submitted but not yet voted
        show up. No papers that have been voted show up.
        '''
        response = auth_client.get(url_for('main.submit'))
        for paper in Paper.query.filter(Paper.voted == None).all():
            assert bytes(paper.title + '<', 'utf-8') in response.data
        for paper in Paper.query.filter(Paper.voted != None).all():
            assert not bytes(paper.title + '<', 'utf-8') in response.data

@pytest.mark.usefixtures('auth_client')
class TestHistory():
    def test_history_access(self, auth_client):
        '''
        Logged in user is able to access the history page.
        '''
        response = auth_client.get(url_for('main.history'))
        assert response.status_code == 200
        assert b'History' in response.data

    def get_instances(self):
        instances = [datetime.strftime(paper.voted, '%Y-%m-%d') for paper
                         in Paper.query.group_by(Paper.voted).all()
                         if paper.voted != None]
        return instances
        
    def test_history_list(self, auth_client):
        '''
        History page displays a link for each vote instance.
        '''
        response = auth_client.get(url_for('main.history'))
        instances = self.get_instances()
        for instance in instances:
            assert bytes(instance, 'utf-8') in response.data

    def test_history_links(self, auth_client):
        '''
        History page links work and display appropriate papers.
        '''
        instances = self.get_instances()
        for instance in instances:
            response = auth_client.get(url_for('main.history',
                                                   week=instance))
            assert response.status_code == 200
            assert b'Votes from %r' % (instance)
            date = datetime.strptime(instance, '%Y-%m-%d')
            papers = Paper.query.filter(Paper.voted == date).all()
            for paper in papers:
                assert bytes(paper.title, 'utf-8') in response.data

@pytest.mark.usefixtures('auth_client')
class TestProfile():
    def recent_subs(self, auth_client):
        '''
        All user pages feature their recent paper submissions.
        '''
        for u in User.query.all():
            response = auth_client.get(url_for('main.user',
                                                   username=u.username))
            recent_papers = Paper.query.filter(Paper.subber==u).all()[:8]
            for r in recent_papers:
                assert bytes(r.title, 'utf-8') in response.data

@pytest.mark.usefixtures('auth_client')
class TestSubmit():
    def submit(self, auth_client):
        response = auth_client.post(url_for('main.submit'), data=dict(
            link='https://arxiv.org/abs/1912.11301',
            comment='testing comment'), follow_redirects=True)
        assert response.status_code == 200
        def check(response):
            assert b'Near-Infrared Polarimetry' in response.data
            assert b'1912.11301' in response.data
            assert b'outer circumbinary disk' in response.data
            assert b'tian Thalmann, Edwin L. Turner' in response.data
        check(response)
        response = auth_client.get(url_for('main.vote'))
        check(response)
        response = auth_client.get(url_for('main.user',
                                        username=current_user.username))
        check(response)
        response = auth_client.post(url_for('main.search'), data=dict(
                                        title='Polarimetry'))
        check(response)

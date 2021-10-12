import uuid
from flask import current_app
from app import db, login
from datetime import datetime, timedelta
from time import time
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    firstname = db.Column(db.String(64))
    lastname = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    password_hold = db.Column(db.String(128))
    retired = db.Column(db.Boolean, default=False)
    hp = db.Column(db.Integer, default=0)

    uploads = db.relationship("Upload", backref='uploader', lazy=True)
    comments = db.relationship("Comment", backref='commenter', lazy=True)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password, *option):
        if not option:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hold = generate_password_hash(password)
            self.password_hash = 'waiting'

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        token = jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'],
            algorithm='HS256').decode('utf-8')
        return token

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def sumpoints(self):
        sp = 0
        sp += 5 * len(self.subs)
        sp += 10 * len(self.vols)
        return sp

    def hotpoints(self):
        hp = 0
        def calc(which):
            nonlocal hp
            for p in list(Paper.query.filter(which[0] == self)
                          .filter(getattr(Paper, which[1])
                                 >= (datetime.now()
                                     - timedelta(weeks=7))).all()):
                if getattr(p, which[1]):
                    lag = datetime.now().date() - getattr(p, which[1])
                    lag = lag.days/7
                    hp += 5 * ((3/4)**(lag))
        calc([Paper.subber, 'timestamp'])
        calc([Paper.volunteer, 'voted'])
        hp = int(hp)
        return hp


class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140))
    timestamp = db.Column(db.Date, index=True, default=datetime.utcnow)
    link = db.Column(db.String(140))
    pdf_url = db.Column(db.String(140))
    abstract = db.Column(db.String(512))
    authors = db.Column(db.String(256))
    voted = db.Column(db.Date)
    score_n = db.Column(db.Integer)
    score_d = db.Column(db.Integer)
    # comment = db.Column(db.String(256))
    
    # Relationships
    subber_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    volunteer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    vol_later_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    subber = db.relationship('User', backref='subs',
                             foreign_keys=[subber_id])
    volunteer = db.relationship('User', backref='vols',
                             foreign_keys=[volunteer_id])
    vol_later = db.relationship('User', backref='later_vols',
                                 foreign_keys=[vol_later_id])
    comments = db.relationship("Comment", backref='paper', lazy=True)

    def __repr__(self):
        return '<Paper {}>'.format(self.title)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    text = db.Column(db.String(512))
    commenter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id'), nullable=False)

    # Relationships
    upload = db.relationship("Upload", backref='comment', uselist=False)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    text = db.Column(db.String(512))

    # Relationships
    announcer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    announcer = db.relationship('User', backref='anns', foreign_keys=[announcer_id])


class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    internal_filename = db.Column(db.String(140))
    external_filename = db.Column(db.String(140))
    user_filename = db.Column(db.String(140))

    # Relationships
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

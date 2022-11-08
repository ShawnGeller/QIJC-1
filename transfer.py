import sqlite3
import sys
from werkzeug.security import generate_password_hash
from secrets import token_hex

path = 'data.sqlite'

class DB_Maker(object):
    '''
    These functions open the old database and rewrite it
    to work with the new application. It's chunky as heck
    but it gets the job done. Once we're ready to go, 
    it should only need to happen once.

    After that point, if new fields are added to the database,
    they'll need to be either added by hand or something like
    flask-migrate will need to be implemented. Probably
    flask-migrate, because doing it by hand is a pain in the ass.
    The only reason it's not already implemented, is because
    we need the database configuration to be set up for 
    this migration vvvvvvvvvvv
    '''

    
    def __init__(self, db_path):
        self.con = sqlite3.connect(db_path)
        self.cur = self.con.cursor()
        self.con.execute('PRAGMA foreign_keys = ON;')

    def remove_UP(self):
        self.cur.execute('DROP TABLE IF EXISTS Paper;')
        self.cur.execute('DROP TABLE IF EXISTS User;')
        self.cur.execute('DROP TABLE IF EXISTS cat_comments;')
        self.con.commit()

    def create_tables(self):
        self.create_user = '''
        CREATE TABLE User (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        firstname TEXT,
        lastname TEXT,
        email TEXT UNIQUE,
        password_hash TEXT,
        password_hold TEXT,
        admin INTEGER,
        retired INTEGER DEFAULT 0,
        hp INTEGER DEFAULT 0
        );'''
        self.cur.execute(self.create_user)
        self.create_paper = '''
        CREATE TABLE Paper (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        timestamp TEXT,
        link TEXT,
        abstract TEXT,
        authors TEXT,
        voted TEXT,
        score_n INTEGER,
        score_d INTEGER,
        comment TEXT,
        subber_id INTEGER,
        volunteer_id INTEGER,
        vol_later_id INTEGER,
        FOREIGN KEY (subber_id) REFERENCES User (id),
        FOREIGN KEY (volunteer_id) REFERENCES User (id),
        FOREIGN KEY (vol_later_id) REFERENCES User (id)
        );'''
        self.cur.execute(self.create_paper)
        print('Created.')

    def comments(self):
        self.create_comments = '''
        CREATE TABLE cat_comments (
        id INTEGER PRIMARY KEY,
        comment TEXT);'''
        self.cur.execute(self.create_comments)
        self.fill_comments = '''
        INSERT INTO cat_comments (id, comment)
        SELECT abstracts.id,
        GROUP_CONCAT(firstname || ": " || comment, "\n")
        FROM abstracts
        LEFT JOIN comments
        ON comments.id == abstracts.id
        LEFT JOIN users
        ON comments.commenter == users.username
        GROUP BY abstracts.id
        ;'''
        self.cur.execute(self.fill_comments)
        print('Comment table prepped.')

    def populate(self):
        self.populate_user = '''
        INSERT INTO User (username, firstname, lastname, email, password_hash, retired)
        SELECT username, firstname, lastname, email,
        '{}',
        users.retired
        FROM users;'''.format(generate_password_hash(token_hex(16)))
        self.cur.execute(self.populate_user)
        self.con.commit()
        self.populate_paper = '''
        INSERT INTO Paper (title, timestamp, link, abstract, voted,
        score_n, score_d, authors, comment, subber_id, volunteer_id)
        SELECT title, substr(subtime, 0, 11), url, abstract,
        substr(date, 0, 11), votenumerator, votedenominator, authors,
        comment, sub.id, vol.id
        FROM abstracts
        LEFT JOIN cat_comments ON cat_comments.id = abstracts.id
        LEFT JOIN weeks ON weeks.number == abstracts.week
        LEFT JOIN User AS sub ON abstracts.submitter = sub.username
        LEFT JOIN User AS vol ON abstracts.volunteer = vol.username
        ;'''
        self.cur.execute(self.populate_paper)
        print('Populated.')        

    def add_users(self):
        pass_hash = 'pbkdf2:sha256:150000$AhNOznap$fe407dfc7307' \
            + 'fa36a3f593efe40fe880a7fecb8926205d59666de4f207c0fc65'
        self.add_someone='''
        INSERT INTO User (
        username, firstname, lastname, password_hash, admin)
        VALUES (?,?,?,?,1);'''
        self.cur.execute(self.add_someone,
                         ('austin', 'austin', 'weisgrau', pass_hash))
        q = ("UPDATE User SET email='austinweisgrau@gmail.com' "
                 + "WHERE username=='austin'")
        self.cur.execute(q)
        def make_admin(username):
            self.cur.execute('UPDATE User SET admin=1 WHERE username==?;',
                                (username,))
        make_admin('sglancy')
        make_admin('knill')
        make_admin('austin')
        make_admin('sgeller')

    def do_it(self):
        try:
            self.remove_UP()
            self.create_tables()
            self.comments()
            self.populate()
            self.add_users()
        except sqlite3.OperationalError as err:
            print('Error: ', err)
        self.con.commit()
        self.con.close()

if __name__ == '__main__':
    db = DB_Maker(path)
    db.do_it()
    print('Finished.')


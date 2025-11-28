from flask import Flask, current_app
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_session import Session
import logging
from logging.handlers import RotatingFileHandler
import os

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
mail = Mail()
bootstrap = Bootstrap()
session = Session()


def create_app(config_class=Config):
    '''
    This application factory returns a Flask app
    with all the modules initalized.
    This kind of setup is useful for testing.
    The app is broken up into 3 blueprints.
    '''
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    session.init_app(app)

    # ensure logs directory exists and add rotating file handler
    logs_path = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(logs_path, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(logs_path, 'qijc.log'),
        maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('QIJC app starting')

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app import models

    return app

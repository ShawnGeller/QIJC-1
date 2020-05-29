from flask import Flask, current_app
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
#login.login_message = _l('Please log in to access this page.')

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app import models

    return app

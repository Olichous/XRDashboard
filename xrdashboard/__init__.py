from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO


db = SQLAlchemy()
socketio = SocketIO(async_mode="threading")

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
    app.config['SECRET_KEY'] = 'change-this-key'

    db.init_app(app)
    socketio.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    return app

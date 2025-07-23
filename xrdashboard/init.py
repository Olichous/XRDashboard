import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO(async_mode="threading")

def create_app():
    app = Flask(__name__, template_folder=os.path.abspath("templates"))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
    app.config['SECRET_KEY'] = 'change-this-key'

    db.init_app(app)
    socketio.init_app(app)

    # Importe les modèles AVANT de créer les tables !
    from xrdashboard import models

    with app.app_context():
        db.create_all()
        print("✔️ Tables SQLite vérifiées/créées automatiquement.")

    from .routes import main
    app.register_blueprint(main)

    return app

# xrdashboard/models.py

from xrdashboard import db

class ConsoleServer(db.Model):
    __tablename__ = 'console_server'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)  # Nom logique (ex: avocent1)
    ip = db.Column(db.String(64), nullable=False)
    type = db.Column(db.String(32), nullable=False)   # 'Avocent', 'Opengear', etc.

    # Equipements liés
    equipments = db.relationship('Equipment', back_populates='console_server')

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(128), nullable=False)
    model = db.Column(db.String(128))
    version = db.Column(db.String(128))
    mgmt_ip = db.Column(db.String(64), nullable=False)
    serial_number = db.Column(db.String(128))
    console_server_id = db.Column(db.Integer, db.ForeignKey('console_server.id'))
    console_port = db.Column(db.String(32))
    iso_filename = db.Column(db.String(256), default="")
    console_server = db.relationship('ConsoleServer', back_populates='equipments')
    snapshots = db.relationship('Snapshot', back_populates='equipment', cascade='all, delete')

class Snapshot(db.Model):
    __tablename__ = 'snapshot'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'))
    file_path = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime)

    equipment = db.relationship('Equipment', back_populates='snapshots')

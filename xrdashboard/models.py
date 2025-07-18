from . import db

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(128))
    model = db.Column(db.String(128))
    version = db.Column(db.String(128))
    mgmt_ip = db.Column(db.String(64))

class Snapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'))
    file_path = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime)
    equipment = db.relationship('Equipment', backref='snapshots')

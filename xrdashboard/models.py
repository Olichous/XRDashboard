from . import db

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(128))
    model = db.Column(db.String(128))
    version = db.Column(db.String(128))
    mgmt_ip = db.Column(db.String(64))

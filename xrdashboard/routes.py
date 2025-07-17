from flask import Blueprint, render_template, request, jsonify
from threading import Thread
from flask_socketio import join_room
from . import db, socketio
from .models import Equipment
from .utils import ping_device, fetch_device_info, update_device

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')


@main.route('/console/<int:eq_id>')
def console(eq_id):
    return render_template('console.html', eq_id=eq_id)

@main.route('/api/equipment', methods=['GET', 'POST'])
def equipment_list():
    if request.method == 'POST':
        data = request.json
        hostname, model, version = fetch_device_info(data['mgmt_ip'])
        eq = Equipment(hostname=hostname, model=model, version=version, mgmt_ip=data['mgmt_ip'])
        db.session.add(eq)
        db.session.commit()
        return jsonify({'id': eq.id}), 201
    else:
        equipment = Equipment.query.all()
        result = []
        for eq in equipment:
            status = ping_device(eq.mgmt_ip)
            result.append({
                'id': eq.id,
                'hostname': eq.hostname,
                'model': eq.model,
                'version': eq.version,
                'mgmt_ip': eq.mgmt_ip,
                'status': status
            })
        return jsonify(result)

@main.route('/api/upload', methods=['POST'])
def upload_image():
    file = request.files['file']
    file.save(f'uploads/{file.filename}')
    return '', 204

@socketio.on('join')
def on_join(room):
    join_room(str(room))

@main.route('/api/update/<int:eq_id>', methods=['POST'])
def update_equipment(eq_id):
    eq = Equipment.query.get_or_404(eq_id)

    def log(msg):
        socketio.emit('log', msg, room=str(eq_id))

    def worker():
        update_device(eq.mgmt_ip, log)

    Thread(target=worker, daemon=True).start()
    return jsonify({'status': 'scheduled'})

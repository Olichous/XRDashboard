from flask import Blueprint, render_template, request, jsonify, send_file
from threading import Thread
from flask_socketio import join_room
from . import db, socketio
from .models import Equipment, Snapshot
from .utils import ping_device, fetch_device_info, update_device
from .snapshot import take_snapshot
from .ssh_utils import reboot_to_pxe
from .ztp import generate_script
from .dhcp import generate_config
import datetime

main = Blueprint("main", __name__)

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



@main.route('/api/snapshot/<int:eq_id>', methods=['POST'])
def snapshot_device(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    data = request.json
    path = take_snapshot(eq.mgmt_ip, data['username'], data['password'])
    snap = Snapshot(equipment_id=eq.id, file_path=str(path), timestamp=datetime.datetime.utcnow())
    db.session.add(snap)
    db.session.commit()
    return jsonify({'snapshot_id': snap.id}), 201


@main.route('/api/download/<int:snap_id>')
def download_snapshot(snap_id):
    snap = Snapshot.query.get_or_404(snap_id)
    return send_file(snap.file_path, as_attachment=True)


@main.route('/api/reboot/<int:eq_id>', methods=['POST'])
def reboot_device(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    data = request.json
    Thread(target=reboot_to_pxe, args=(eq.mgmt_ip, data['username'], data['password']), daemon=True).start()
    return jsonify({'status': 'rebooting'})


@main.route('/ztp/<hostname>.sh')
def ztp_script(hostname):
    eq = Equipment.query.filter_by(hostname=hostname).first_or_404()
    script = generate_script(hostname, eq)
    return script, 200, {'Content-Type': 'text/plain'}


@main.route('/api/dhcp')
def dhcp_config():
    equipment = Equipment.query.all()
    config = generate_config(equipment)
    return config, 200, {'Content-Type': 'text/plain'}

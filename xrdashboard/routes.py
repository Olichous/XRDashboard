from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename
from . import db
from .models import Equipment, ConsoleServer
import os
import re
import ipaddress
import subprocess
import hashlib
import json

main = Blueprint("main", __name__)

ZTPCFG = {
    "enabled": False,
    "relay": False,
    "network": "",
    "range_start": "",
    "range_end": "",
}

UPLOAD_DIR = "uploads"

def ping_device(ip):
    try:
        import platform
        ping_cmd = ["ping", "-c", "1", "-W", "1", ip] if platform.system() != "Windows" else ["ping", "-n", "1", ip]
        return subprocess.call(ping_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except Exception:
        return False

def smart_ip(subnet, val):
    try:
        # Si val ressemble déjà à une IP, on renvoie tel quel
        ipaddress.IPv4Address(val)
        return val
    except Exception:
        # Sinon, on concatène le subnet et le dernier octet
        base = str(ipaddress.IPv4Network(subnet, strict=False).network_address)
        base_parts = base.split('.')
        return '.'.join(base_parts[:3] + [str(val)])

def generate_config(equipment, relay, network, range_start, range_end):
    out = ["#### DHCP Config ####"]
    out.append("subnet 172.17.0.0 netmask 255.255.0.0 {}")
    if network and range_start and range_end:
        try:
            net = ipaddress.IPv4Network(network, strict=False)
            netmask = net.netmask
            netaddr = net.network_address
            range1 = smart_ip(network, range_start)
            range2 = smart_ip(network, range_end)
            out.append(f"subnet {netaddr} netmask {netmask} {{")
            out.append(f"  range {range1} {range2};")
            out.append(f"  option routers {str(list(net.hosts())[0])};")
            out.append(f"  option domain-name-servers 8.8.8.8;")
            out.append("}")
        except Exception as e:
            out.append(f"# ERROR in subnet config: {e}")
    for eq in equipment:
        out.append(f"host {eq.hostname} {{")
        out.append(f"  fixed-address {eq.mgmt_ip};")
        out.append(f"  option host-name \"{eq.hostname}\";")
        out.append(f"  # serial: {getattr(eq, 'serial_number', '')}")
        out.append("}")
    return "\n".join(out)

def write_dhcp_conf(conf):
    with open("/etc/dhcp/dhcpd.conf", "w") as f:
        f.write(conf)

def start_dhcp_server():
    subprocess.run(["service", "isc-dhcp-server", "restart"], check=False)

def stop_dhcp_server():
    subprocess.run(["service", "isc-dhcp-server", "stop"], check=False)

@main.route('/api/equipment', methods=['GET', 'POST'])
def equipment_list():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        hostname = data.get('hostname')
        mgmt_ip = data.get('mgmt_ip')
        serial_number = data.get('serial_number', "")
        model = data.get('model', "")
        mac = data.get('mac', "")
        console_server_id = data.get('console_server_id')
        console_port = data.get('console_port', "")
        ssh_user = data.get('ssh_user', "")
        ssh_pass = data.get('ssh_pass', "")
        if not (hostname and mgmt_ip):
            return jsonify({'error': 'hostname and mgmt_ip required'}), 400
        eq = Equipment(hostname=hostname, mgmt_ip=mgmt_ip, serial_number=serial_number, model=model)
        if hasattr(eq, 'mac'): eq.mac = mac
        if hasattr(eq, 'console_server_id'): eq.console_server_id = console_server_id
        if hasattr(eq, 'console_port'): eq.console_port = console_port
        if hasattr(eq, 'ssh_user'): eq.ssh_user = ssh_user
        if hasattr(eq, 'ssh_pass'): eq.ssh_pass = ssh_pass
        db.session.add(eq)
        db.session.commit()
        # Regénère la conf DHCP (à chaque ajout)
        equipment = Equipment.query.all()
        config = generate_config(
            equipment,
            relay=ZTPCFG["relay"],
            network=ZTPCFG["network"],
            range_start=ZTPCFG["range_start"],
            range_end=ZTPCFG["range_end"],
        )
        write_dhcp_conf(config)
        if ZTPCFG["enabled"]:
            start_dhcp_server()
        return jsonify({'id': eq.id}), 201
    else:
        eqs = Equipment.query.all()
        result = []
        for eq in eqs:
            status = ping_device(eq.mgmt_ip)
            cs = None
            cs_id = getattr(eq, 'console_server_id', None)
            if cs_id:
                cs = ConsoleServer.query.get(cs_id)
            cs_name = cs.name if cs else ""
            result.append({
                'id': eq.id,
                'hostname': eq.hostname,
                'mgmt_ip': eq.mgmt_ip,
                'serial_number': getattr(eq, 'serial_number', ""),
                'model': getattr(eq, 'model', ""),
                'mac': getattr(eq, 'mac', ""),
                'console_server_name': cs_name,
                'console_port': getattr(eq, 'console_port', ""),
                'status': status,
            })
        return jsonify(result)

@main.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
def equipment_delete(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    db.session.delete(eq)
    db.session.commit()
    # Regénère la conf DHCP
    equipment = Equipment.query.all()
    config = generate_config(
        equipment,
        relay=ZTPCFG["relay"],
        network=ZTPCFG["network"],
        range_start=ZTPCFG["range_start"],
        range_end=ZTPCFG["range_end"],
    )
    write_dhcp_conf(config)
    if ZTPCFG["enabled"]:
        start_dhcp_server()
    return '', 204

@main.route('/api/update/<int:eq_id>', methods=['POST'])
def update_equipment(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    # Ici tu pourrais lancer une vraie upgrade : pour l’instant, regénère conf DHCP
    equipment = Equipment.query.all()
    config = generate_config(
        equipment,
        relay=ZTPCFG["relay"],
        network=ZTPCFG["network"],
        range_start=ZTPCFG["range_start"],
        range_end=ZTPCFG["range_end"],
    )
    write_dhcp_conf(config)
    if ZTPCFG["enabled"]:
        start_dhcp_server()
    return jsonify({"status": "ok"})

# ConsoleServers CRUD
@main.route('/api/consoleservers', methods=['GET', 'POST'])
def consoleserver_list():
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        ip = data.get('ip')
        type_ = data.get('type')
        cs = ConsoleServer(name=name, ip=ip, type=type_)
        db.session.add(cs)
        db.session.commit()
        return '', 201
    else:
        css = ConsoleServer.query.all()
        return jsonify([{"id": cs.id, "name": cs.name, "ip": cs.ip, "type": cs.type} for cs in css])

@main.route('/api/consoleservers/<int:cs_id>', methods=['DELETE'])
def consoleserver_delete(cs_id):
    cs = ConsoleServer.query.get_or_404(cs_id)
    db.session.delete(cs)
    db.session.commit()
    return '', 204

# Images (upload, list, delete)
@main.route('/api/upload', methods=['POST'])
def upload_image():
    file = request.files['file']
    eq_id = request.form.get('equipment_id', "")
    filename = secure_filename(file.filename)
    type_, version = "Generic", ""
    if "NCS" in filename.upper():
        type_ = "NCS"
    elif "ASR" in filename.upper():
        type_ = "ASR"
    m = re.search(r'(\d+\.\d+\.\d+)', filename)
    if m:
        version = m.group(1)
    folder = os.path.join(UPLOAD_DIR, type_, version if version else "unknown")
    os.makedirs(folder, exist_ok=True)
    fpath = os.path.join(folder, filename)
    file.save(fpath)
    # Calcul md5sum sur l’iso
    md5sum = ""
    if filename.endswith(".iso"):
        with open(fpath, "rb") as f:
            md5sum = hashlib.md5(f.read()).hexdigest()
    # Stockage d’un json avec l’association image<->equipement
    json_path = os.path.join(folder, "images.json")
    imgdata = []
    if os.path.exists(json_path):
        imgdata = json.load(open(json_path))
    imgdata.append({"filename": filename, "equipment": eq_id, "md5sum": md5sum})
    with open(json_path, "w") as jf:
        json.dump(imgdata, jf)
    return '', 200

@main.route('/api/images', methods=['GET'])
def list_images():
    results = []
    for root, dirs, files in os.walk(UPLOAD_DIR):
        for file in files:
            if file.endswith((".iso", ".img", ".tar", ".zip")):
                fpath = os.path.join(root, file)
                rel = os.path.relpath(fpath, UPLOAD_DIR)
                type_ = "Generic"
                version = ""
                if "NCS" in file.upper():
                    type_ = "NCS"
                elif "ASR" in file.upper():
                    type_ = "ASR"
                m = re.search(r'(\d+\.\d+\.\d+)', file)
                if m:
                    version = m.group(1)
                md5sum = ""
                if file.endswith(".iso"):
                    with open(fpath, "rb") as f:
                        md5sum = hashlib.md5(f.read()).hexdigest()
                results.append({"filename": rel, "type": type_, "version": version, "equipment": "", "md5sum": md5sum})
    return jsonify(results)

@main.route('/api/image/<path:filename>', methods=['DELETE'])
def delete_image(filename):
    fpath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(fpath):
        os.remove(fpath)
    return '', 204

# DHCP config/preview (ZTP)
@main.route('/api/ztp/dhcp-preview', methods=['GET'])
def ztp_dhcp_preview():
    equipment = Equipment.query.all()
    config = generate_config(
        equipment,
        relay=ZTPCFG["relay"],
        network=ZTPCFG["network"],
        range_start=ZTPCFG["range_start"],
        range_end=ZTPCFG["range_end"],
    )
    return config

@main.route('/api/ztp/config', methods=['POST'])
def ztp_config():
    data = request.json
    ZTPCFG["enabled"] = data.get("enabled", False)
    ZTPCFG["relay"] = data.get("relay", False)
    ZTPCFG["network"] = data.get("network", "")
    ZTPCFG["range_start"] = data.get("range_start", "")
    ZTPCFG["range_end"] = data.get("range_end", "")
    # Écrit et redémarre le DHCP
    equipment = Equipment.query.all()
    config = generate_config(
        equipment,
        relay=ZTPCFG["relay"],
        network=ZTPCFG["network"],
        range_start=ZTPCFG["range_start"],
        range_end=ZTPCFG["range_end"],
    )
    write_dhcp_conf(config)
    if ZTPCFG["enabled"]:
        start_dhcp_server()
    else:
        stop_dhcp_server()
    return '', 200

# Statut DHCP pour le dashboard (UP/DOWN)
@main.route('/api/dhcp/status')
def dhcp_status():
    try:
        output = subprocess.check_output("ps -ef | grep [d]hcpd", shell=True).decode()
        running = 'dhcpd' in output
    except Exception:
        running = False
    return jsonify({"up": running})

@main.route('/')
def index():
    return render_template('index.html')

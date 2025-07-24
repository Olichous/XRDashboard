from flask import Blueprint, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from . import db
from .models import Equipment, ConsoleServer
import os
import re
import ipaddress
import subprocess
import hashlib
import json
import paramiko

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
        ipaddress.IPv4Address(val)
        return val
    except Exception:
        base = str(ipaddress.IPv4Network(subnet, strict=False).network_address)
        base_parts = base.split('.')
        return '.'.join(base_parts[:3] + [str(val)])

def get_server_ip():
    # Essaie de trouver l'IP publique du serveur
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def generate_config(equipment, relay, network, range_start, range_end):
    out = ["#### DHCP Config ####"]
    out.append("subnet 172.17.0.0 netmask 255.255.0.0 {}")
    # Pool DHCP
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

    # Host entries avancées
    server_ip = get_server_ip()
    for eq in equipment:
        mac = getattr(eq, 'mac', '00:00:00:00:00:00')
        iso_name = getattr(eq, 'iso_filename', '') or 'default.iso'
        # Filenames pour iPXE/Config
        out.append(f"host {eq.hostname} {{")
        out.append(f"  hardware ethernet {mac};")
        out.append(f"  fixed-address {eq.mgmt_ip};")
        out.append(f"  option host-name \"{eq.hostname}\";")
        out.append(f"  # serial: {getattr(eq, 'serial_number', '')}")
        out.append(f"""  if exists user-class and option user-class = "iPXE" {{
    filename = "http://{server_ip}/{iso_name}";
  }} else if exists user-class and option user-class = "exr-config" {{
    filename = "http://{server_ip}/uploads/{eq.hostname}/{eq.serial_number}/ztp.sh";
  }}
""")
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
        console_server_id = data.get('console_server_id')
        console_port = data.get('console_port', "")
        ssh_user = data.get('ssh_user', "")
        ssh_pass = data.get('ssh_pass', "")
        if not (hostname and mgmt_ip and ssh_user and ssh_pass):
            return jsonify({'error': 'hostname, mgmt_ip, ssh_user and ssh_pass required'}), 400

        # SSH à la volée, récupération Serial & running-config
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(mgmt_ip, username=ssh_user, password=ssh_pass, look_for_keys=False, timeout=5)
            # Serial number
            stdin, stdout, stderr = client.exec_command("show inventory | inc SN:")
            serial_number = ""
            for line in stdout:
                if "SN:" in line:
                    serial_number = line.strip().split("SN:")[-1].strip()
                    break
            # Running-config
            stdin, stdout, stderr = client.exec_command("show running-config")
            running_conf = stdout.read().decode('utf-8')
            client.close()
            if not serial_number:
                return jsonify({'error': 'Impossible de récupérer le serial number'}), 500
        except Exception as e:
            return jsonify({'error': f'SSH failed: {e}'}), 500

        # Création DB
        eq = Equipment(hostname=hostname, mgmt_ip=mgmt_ip, serial_number=serial_number)
        if hasattr(eq, 'console_server_id'): eq.console_server_id = console_server_id
        if hasattr(eq, 'console_port'): eq.console_port = console_port
        db.session.add(eq)
        db.session.commit()

        # Stockage config sur disque
        folder = os.path.join(UPLOAD_DIR, hostname, serial_number)
        os.makedirs(folder, exist_ok=True)
        conf_file = os.path.join(folder, "running-config.txt")
        with open(conf_file, "w") as f:
            f.write(running_conf)

        # Génère script ZTP.sh pour ce routeur (à adapter selon ton besoin)
        ztp_script = os.path.join(folder, "ztp.sh")
        with open(ztp_script, "w") as f:
            f.write("#!/bin/bash\n# script ZTP pour le routeur\n")

        # Génère DHCP + restart
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

@main.route('/uploads/<hostname>/<serial_number>/<filename>')
def download_config(hostname, serial_number, filename):
    folder = os.path.join(UPLOAD_DIR, hostname, serial_number)
    return send_from_directory(folder, filename)

@main.route('/api/update/<int:eq_id>', methods=['POST'])
def update_equipment(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    data = request.json or {}
    iso_filename = data.get('image')
    if hasattr(eq, 'iso_filename'):
        eq.iso_filename = iso_filename or ""
        db.session.commit()
    # Génère DHCP + restart
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

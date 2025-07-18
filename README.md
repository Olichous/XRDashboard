# XR Dashboard

XR Dashboard is a simple automation lab for Cisco IOS-XR devices. It provides:

- Inventory management stored in SQLite
- Snapshot of running configuration and interface status
- Real-time console logs during software updates
- Basic PXE reboot and ZTP script generation
- DHCP configuration generator

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python db_create.py
python app.py
```

## Docker

```bash
docker build -t xrdashboard .
```

The API listens on port **5050** and ZTP scripts are served at `/ztp/<hostname>.sh`.

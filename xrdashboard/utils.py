import subprocess
import time
from ping3 import ping


def ping_device(ip):
    try:
        result = ping(ip, timeout=1)
        return result is not None
    except Exception:
        return False


def fetch_device_info(ip):
    # Placeholder for real device query
    hostname = f'device-{ip}'
    model = 'IOS-XR'
    version = '7.9.1'
    return hostname, model, version


def update_device(ip, log_callback):
    """Simulate an update and emit logs through the callback."""
    steps = [
        "Copying image",
        "Checking integrity",
        "Installing packages",
        "Reloading device",
        "Upgrade complete"
    ]
    for step in steps:
        log_callback(step)
        time.sleep(1)


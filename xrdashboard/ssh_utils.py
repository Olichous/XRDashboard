import paramiko


def run_commands(ip: str, username: str, password: str, commands):
    """Run a list of commands over SSH and return outputs."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password, look_for_keys=False)
    output = {}
    for cmd in commands:
        stdin, stdout, stderr = client.exec_command(cmd)
        output[cmd] = stdout.read().decode()
    client.close()
    return output


def reboot_to_pxe(ip: str, username: str, password: str):
    commands = [
        "admin",
        "hw-module location all bootmedia network reload"
    ]
    run_commands(ip, username, password, commands)

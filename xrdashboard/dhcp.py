from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates' / 'dhcp'
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_config(equipment_list):
    template = env.get_template('dhcp.conf.j2')
    return template.render(equipment=equipment_list)

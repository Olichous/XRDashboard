from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates' / 'ztp'
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_script(hostname: str, equipment):
    template = env.get_template('script.sh.j2')
    return template.render(hostname=hostname, equipment=equipment)

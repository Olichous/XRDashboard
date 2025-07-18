from pathlib import Path
import textfsm

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates' / 'textfsm'


def parse_output(command: str, output: str):
    template_file = TEMPLATE_DIR / f"{command.replace(' ', '_')}.textfsm"
    if not template_file.exists():
        return output
    with open(template_file) as f:
        fsm = textfsm.TextFSM(f)
        return [dict(zip(fsm.header, row)) for row in fsm.ParseText(output)]

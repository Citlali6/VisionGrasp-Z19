"""Read the single register authority as data; never map a device."""
import json
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
_definition = json.loads((_root/'fpga/system_pspl/registers.json').read_text(encoding='utf-8'))
COMMON = _definition['common']
VIDEO = _definition['video']
AUDIO = _definition['audio']

"""Future explicit regeneration of register/address projections, no hardware.

Not executed in the 2026-10-30 delivery. JSON is the definition authority;
checked-in projections were authored and compared by textual source review.
"""
import json
from pathlib import Path


def generate(root):
    root = Path(root).resolve()
    profile_dir = root / 'fpga/system_pspl'
    regs = json.loads((profile_dir/'registers.json').read_text(encoding='utf-8'))
    c_lines = ['/* Derived from fpga/system_pspl/registers.json. */',
               '#ifndef VG_PSPL_REGISTERS_H', '#define VG_PSPL_REGISTERS_H']
    sv_lines = ['// Derived from fpga/system_pspl/registers.json; include inside module.']
    for group, prefix in [('common', 'R'), ('video', 'V'), ('audio', 'A')]:
        for name, offset in regs[group].items():
            if not isinstance(offset, int) or offset % 4 or not 0 <= offset < 4096:
                raise ValueError('Invalid register definition')
            c_lines.append('#define PSPL_%s_%s 0x%03xu' % (prefix, name, offset))
            sv_lines.append("localparam [11:0] PSPL_%s_%s = 12'h%03x;" % (prefix, name, offset))
    c_lines.append('#endif')
    (root/'host/libpspl/include/registers.h').write_text('\n'.join(c_lines)+'\n', encoding='utf-8')
    (profile_dir/'rtl/registers.svh').write_text('\n'.join(sv_lines)+'\n', encoding='utf-8')
    profile = json.loads((profile_dir/'profile.json').read_text(encoding='utf-8'))
    tcl = ['# Derived from profile.json.', 'set device_part {%s}' % profile['part'],
           'set logic_clock_mhz %s' % profile['clock_mhz']]
    for name, device in profile['devices'].items():
        tcl.append('set %s_base %s' % (name, device['base']))
        tcl.append('set %s_range %d' % (name, device['range']))
    (profile_dir/'profile.tcl').write_text('\n'.join(tcl)+'\n', encoding='utf-8')


if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[2])

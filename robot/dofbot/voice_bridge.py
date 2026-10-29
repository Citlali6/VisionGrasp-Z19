"""Voice protocol and class/audio mappings for the standalone sorting session.

Extracted without behavior changes from the validated 2026-10-29 bridge.
This module has no application server, hardware access or motion controller.
"""

SINGLE_CLASSES = {
    'Zip_top_can': ('00', '01'), 'Old_school_bag': ('01', '01'),
    'Newspaper': ('02', '01'), 'Book': ('03', '01'),
    'Toilet_paper': ('04', '02'), 'Peach_pit': ('05', '02'),
    'Cigarette_butts': ('06', '02'), 'Disposable_chopsticks': ('07', '02'),
    'Egg_shell': ('08', '03'), 'Apple_core': ('09', '03'),
    'Watermelon_rind': ('10', '03'), 'Fish_bone': ('11', '03'),
    'Expired_tablets': ('12', '04'), 'Expired_cosmetics': ('13', '04'),
    'Used_batteries': ('14', '04'), 'Syringe': ('15', '04'),
}


SINGLE_AUDIO = dict(zip((
    'Zip_top_can', 'Old_school_bag', 'Newspaper', 'Book', 'Syringe',
    'Used_batteries', 'Expired_cosmetics', 'Expired_tablets', 'Fish_bone',
    'Watermelon_rind', 'Apple_core', 'Egg_shell', 'Disposable_chopsticks',
    'Cigarette_butts', 'Peach_pit', 'Toilet_paper'), range(94, 110)))


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        events = []
        while True:
            start = self.buffer.find(b'\xaa\x55')
            if start < 0:
                self.buffer[:] = b'\xaa' if self.buffer[-1:] == b'\xaa' else b''
                break
            del self.buffer[:start]
            if len(self.buffer) < 5:
                break
            wake, command = self.buffer[2:4]
            if self.buffer[4] != 0xfb or wake > 6 or (wake and command):
                del self.buffer[0]
                continue
            frame = bytes(self.buffer[:5])
            del self.buffer[:5]
            events.append((wake, command, frame.hex()))
        return events

from fpga.sort_guard.host.validation import StreamIdentity

IDENTITY = StreamIdentity('fixture-camera', 'fixture-session-1')


def status(sequence=10, *, stamp=100.0, count=100, box=None):
    box = [20, 30, 39, 49] if box is None else box
    result = dict(source='Z19_USB_TO_REAL_PL', frame=sequence,
                  capture_sequence=sequence, pl_sequence=sequence, width=640,
                  height=360, color=1, min_s=100, min_v=80, mask_count=count,
                  bbox=box, published_monotonic=stamp, captured_monotonic=stamp-.1,
                  request_id=95000000, age_s=.1, camera_running=True,
                  request=dict(request_id=95000000, requested_monotonic=95.,
                               color=1, min_s=100, min_v=80, source='fixture'))
    if count:
        result['target'] = dict(state='found', bbox=box.copy(), mask_count=count,
                                frame_sequence=sequence, request_id=95000000)
    else:
        result['target'] = dict(state='not_found', bbox=None)
    return result

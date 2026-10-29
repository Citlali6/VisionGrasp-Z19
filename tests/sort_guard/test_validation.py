import copy
import pytest

from fpga.sort_guard.host.validation import parse_status, ValidationError, StreamIdentity
from .helpers import IDENTITY, status


def parse(value, **kwargs):
    return parse_status(value, identity=IDENTITY, now=100.1, **kwargs)


def test_existing_status_format_and_zero_target_sentinel():
    frame = parse(status())
    assert (frame.sequence, frame.color, frame.bbox) == (10, 1, (20, 30, 39, 49))
    empty = parse(status(count=0, box=[65535, 65535, 0, 0]))
    assert empty.count == 0 and empty.bbox == (0, 0, 0, 0)


@pytest.mark.parametrize('key,value', [
    ('source', 'CPU_DETECTOR'), ('camera_running', False), ('camera_running', 1),
    ('camera_error', 'disconnected'), ('capture_sequence', True),
    ('pl_sequence', 11), ('pl_sequence', -1), ('capture_sequence', 2**32),
    ('width', 0), ('height', 65536), ('color', 0), ('color', 2),
    ('request_id', 42), ('mask_count', -1), ('mask_count', 401),
    ('mask_count', True), ('bbox', [50, 30, 39, 49]),
    ('bbox', [20, 30, 640, 49]), ('bbox', [20, 30, 39., 49]),
    ('age_s', 2.01), ('age_s', -1), ('age_s', float('nan')),
    ('published_monotonic', 100.2), ('captured_monotonic', 94),
    ('captured_monotonic', 97), ('published_monotonic', float('inf')),
    ('camera_id', 'other-camera'), ('session_id', 'old-session'),
    ('min_s', 99), ('min_v', 81),
])
def test_rejects_invalid_or_unpaired_metadata(key, value):
    data = status()
    data[key] = value
    with pytest.raises(ValidationError):
        parse(data)


@pytest.mark.parametrize('key', ['source', 'camera_running', 'request', 'target',
    'capture_sequence', 'pl_sequence', 'frame', 'width', 'height', 'age_s',
    'captured_monotonic', 'published_monotonic', 'mask_count', 'bbox'])
def test_missing_fields_fail_closed(key):
    data = status()
    del data[key]
    with pytest.raises(ValidationError):
        parse(data)


@pytest.mark.parametrize('field,value', [('state', 'stale'), ('state', 'waiting'),
    ('mask_count', 99), ('bbox', [0, 0, 1, 1]), ('frame_sequence', 9),
    ('request_id', 12), ('frame_sequence', True)])
def test_target_view_cannot_override_pl_statistics(field, value):
    data = status()
    data['target'][field] = value
    with pytest.raises(ValidationError):
        parse(data)


def test_identity_must_be_explicit_and_now_uses_source_clock():
    for identity in (None, {}, 'fixture-session'):
        with pytest.raises(ValidationError):
            parse_status(status(), identity=identity, now=100.1)
    with pytest.raises(ValidationError):
        StreamIdentity('', 'a')
    with pytest.raises(ValidationError):
        parse_status(status(), identity=IDENTITY, now=3)
    # A forged low age_s does not override producer timestamp age.
    with pytest.raises(ValidationError):
        parse_status(status(), identity=IDENTITY, now=103)


def test_parse_does_not_mutate_the_status_and_binding_includes_thresholds():
    original = status()
    saved = copy.deepcopy(original)
    a = parse(original)
    assert original == saved
    changed = copy.deepcopy(original)
    changed['request']['min_s'] = changed['min_s'] = 120
    assert a.binding != parse(changed).binding

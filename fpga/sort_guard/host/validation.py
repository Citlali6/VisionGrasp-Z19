"""Validate the existing color preview /status without opening any device.

The existing endpoint has no authenticated camera/session identifier. Its caller
must supply an independently trusted acquisition identity; JSON alone is not an
identity proof. All timestamps passed here use the producer's monotonic clock.
"""
from dataclasses import dataclass
import math


class ValidationError(ValueError):
    pass


def integer(value, name, low=0, high=0xffffffff):
    if type(value) is not int or not low <= value <= high:
        raise ValidationError('%s must be an integer in [%s, %s]' % (name, low, high))
    return value


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValidationError(name+' must be a finite nonnegative number')
    return float(value)


@dataclass(frozen=True)
class StreamIdentity:
    camera_id: str
    session_id: str

    def __post_init__(self):
        for name in ('camera_id', 'session_id'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValidationError(name+' must be an explicit nonempty acquisition identity')


@dataclass(frozen=True)
class Frame:
    identity: StreamIdentity
    request_id: int
    requested_at: float
    sequence: int
    frame: int
    width: int
    height: int
    color: int
    min_s: int
    min_v: int
    count: int
    bbox: tuple
    captured_at: float
    published_at: float

    @property
    def binding(self):
        return (self.identity, self.request_id, self.requested_at, self.color,
                self.width, self.height, self.min_s, self.min_v)


def parse_status(status, *, identity, now, max_age=2.0):
    """Parse current PL statistics, including valid zero-target frames.

    Reject absent/false camera supervision and untrusted freshness. ``now`` is
    producer-monotonic time supplied by a local supervisor or offline fixture,
    never this PC's unrelated monotonic clock. Zero-target sentinel boxes are
    converted to zeros only after the endpoint's not_found state is confirmed.
    """
    if not isinstance(identity, StreamIdentity):
        raise ValidationError('explicit StreamIdentity is required')
    if type(status) is not dict:
        raise ValidationError('status must be an object')
    now, max_age = finite(now, 'now'), finite(max_age, 'max_age')
    if not 0 < max_age <= 2:
        raise ValidationError('max_age must be in (0, 2] seconds')
    if status.get('source') != 'Z19_USB_TO_REAL_PL':
        raise ValidationError('wrong PL statistics source')
    if status.get('camera_running') is not True or status.get('camera_error'):
        raise ValidationError('a healthy supervised camera is required')
    # Optional explicit identifiers must agree; they never replace the binding.
    for key in ('camera_id', 'session_id'):
        if key in status and status[key] != getattr(identity, key):
            raise ValidationError(key+' differs from acquisition identity')
    request, target = status.get('request'), status.get('target')
    if type(request) is not dict or type(target) is not dict:
        raise ValidationError('request and target objects are required')
    sequence = integer(status.get('capture_sequence'), 'capture_sequence')
    if integer(status.get('pl_sequence'), 'pl_sequence') != sequence:
        raise ValidationError('capture_sequence and pl_sequence do not match')
    frame = integer(status.get('frame'), 'frame')
    width = integer(status.get('width'), 'width', 1, 65535)
    height = integer(status.get('height'), 'height', 1, 65535)
    color = integer(status.get('color'), 'color', 1, 3)
    request_id = integer(status.get('request_id'), 'request_id', 1, 0xffffffffffffffff)
    if integer(request.get('request_id'), 'request.request_id', 1, 0xffffffffffffffff) != request_id:
        raise ValidationError('request_id does not match current request')
    if integer(request.get('color'), 'request.color', 1, 3) != color:
        raise ValidationError('color does not match current request')
    min_s = integer(status.get('min_s'), 'min_s', 0, 255)
    min_v = integer(status.get('min_v'), 'min_v', 0, 255)
    for key, value in (('min_s', min_s), ('min_v', min_v)):
        if integer(request.get(key), 'request.'+key, 0, 255) != value:
            raise ValidationError(key+' differs from current request')
    requested = finite(request.get('requested_monotonic'), 'requested_monotonic')
    captured = finite(status.get('captured_monotonic'), 'captured_monotonic')
    published = finite(status.get('published_monotonic'), 'published_monotonic')
    age = finite(status.get('age_s'), 'age_s')
    if not requested <= captured <= published <= now:
        raise ValidationError('timestamps are out of order or precede the request')
    if max(age, now-published, now-captured) > max_age:
        raise ValidationError('stale frame')
    count = integer(status.get('mask_count'), 'mask_count', 0, width*height)
    box = status.get('bbox')
    if type(box) is not list or len(box) != 4:
        raise ValidationError('bbox must contain four coordinates')
    box = tuple(integer(value, 'bbox coordinate', 0, 65535) for value in box)
    if count:
        x0, y0, x1, y1 = box
        if not (x0 <= x1 < width and y0 <= y1 < height):
            raise ValidationError('bbox is outside the frame or reversed')
        if count > (x1-x0+1)*(y1-y0+1):
            raise ValidationError('mask_count exceeds the bounding rectangle area')
        if (target.get('state') != 'found' or target.get('bbox') != list(box)
                or type(target.get('mask_count')) is not int or target['mask_count'] != count
                or type(target.get('frame_sequence')) is not int or target['frame_sequence'] != sequence
                or type(target.get('request_id')) is not int or target['request_id'] != request_id):
            raise ValidationError('target view does not match PL statistics')
    else:
        if target.get('state') != 'not_found' or target.get('bbox') is not None:
            raise ValidationError('zero-target frame must have a not_found view')
        box = (0, 0, 0, 0)
    return Frame(identity, request_id, requested, sequence, frame, width, height,
                 color, min_s, min_v, count, box, captured, published)

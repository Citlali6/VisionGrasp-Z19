"""Typed frame identity shared by acquisition, PL and semantic results."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FrameIdentity:
    camera_id: str
    session_id: str
    frame_id: int
    transform_id: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() or len(v) > 256
               for v in (self.camera_id, self.session_id, self.transform_id)):
            raise ValueError('explicit camera, session and transform identities required')
        if type(self.frame_id) is not int or not 0 <= self.frame_id <= 0xffffffff:
            raise ValueError('frame_id must be uint32')

    def as_dict(self):
        return dict(camera_id=self.camera_id, session_id=self.session_id,
                    frame_id=self.frame_id, transform_id=self.transform_id)


def finite_vector(value, length, name):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(name+' has wrong size')
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError(name+' contains a nonfinite value')
    return result

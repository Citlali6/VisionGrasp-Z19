"""Decode actual Ultralytics Results boxes; NMS belongs to enrolled backend."""
import math
from .class_mapping import business
from .preprocess import restore_vendor_box


def decode_results(results, manifest, identity, width, height):
    if len(results) != 1:
        raise RuntimeError('detector batch/result count differs from one')
    result = results[0]
    if tuple(result.orig_shape) != (480, 640):
        raise RuntimeError('backend returned a different pixel coordinate space')
    if result.boxes is None:
        raise RuntimeError('detect backend did not supply boxes')
    # data rows are post-NMS [x0,y0,x1,y1,confidence,class_id]. Tracking IDs
    # would change this shape and are deliberately rejected.
    rows = result.boxes.data.detach().cpu().tolist()
    detections = []
    for row in rows:
        if len(row) != 6 or not all(math.isfinite(float(v)) for v in row):
            raise RuntimeError('unexpected nonfinite/tracking/raw output tensor')
        x0, y0, x1, y1, confidence, cls = (float(v) for v in row)
        class_id = int(cls)
        if cls != class_id or not 0 <= class_id < len(manifest.names) or not 0 <= confidence <= 1:
            raise RuntimeError('invalid class/confidence output')
        if x1 <= x0 or y1 <= y0:
            raise RuntimeError('reversed or zero-area detector bbox')
        label = manifest.names[class_id]
        mapping = business(label)
        if mapping is None or confidence < manifest.confidence:
            continue
        bbox = restore_vendor_box((x0, y0, x1, y1), width, height)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        detections.append(dict(class_id=class_id, label=label, confidence=confidence,
                               bbox=list(bbox), pixel_center=[(bbox[0]+bbox[2])/2,
                                                              (bbox[1]+bbox[3])/2],
                               **mapping, **identity.as_dict()))
    # Return every object. Only a separately stated unique-target policy may
    # select one for a task; repeated labels are never overwritten in a dict.
    return sorted(detections, key=lambda d: (-d['confidence'], d['class_id'], d['bbox'][0]))

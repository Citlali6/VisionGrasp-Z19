"""Vendor outer resize and RGB/BGR contract; inner letterbox stays with YOLO.

The vendor first resizes to 640x480 BGR, then passes a NumPy image to YOLO.
The enrolled predictor owns stride-aware letterbox, RGB tensor conversion and
division by 255. We never normalize twice or feed display overlays to a model.
"""


def vendor_bgr(rgb):
    import cv2
    import numpy as np
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('model input must be uint8 HWC RGB888')
    if not rgb.shape[0] or not rgb.shape[1]:
        raise ValueError('empty image')
    resized = cv2.resize(rgb, (640, 480), interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(resized[:, :, ::-1])


def restore_vendor_box(box, width, height):
    """Ultralytics Results.xyxy already undoes its internal letterbox.

Only undo the vendor's outer 640x480 resize, preserving the selected source's
pixel space. Raw network xywh tensors must not be passed to this function.
"""
    if width <= 0 or height <= 0:
        raise ValueError('invalid image dimensions')
    x0, y0, x1, y1 = box
    # xyxy is a continuous rectangle: its far edge may equal width/height.
    return (max(0., min(float(width), x0*width/640.)),
            max(0., min(float(height), y0*height/480.)),
            max(0., min(float(width), x1*width/640.)),
            max(0., min(float(height), y1*height/480.)))

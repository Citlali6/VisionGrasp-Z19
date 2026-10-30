"""Explicit image-space transforms and camera-bound planar calibration."""
import math
from .result_types import finite_vector


def homography_point(matrix, point):
    h = finite_vector(matrix, 9, 'homography')
    scale=max(abs(v) for v in h)
    if not scale:
        raise ValueError('zero homography')
    h=tuple(v/scale for v in h)
    x, y = finite_vector(point, 2, 'point')
    denominator = h[6]*x+h[7]*y+h[8]
    if abs(denominator) <= 1e-12:
        raise ValueError('point is on homography horizon')
    result = ((h[0]*x+h[1]*y+h[2])/denominator,
              (h[3]*x+h[4]*y+h[5])/denominator)
    if not all(math.isfinite(v) for v in result):
        raise ValueError('homography produced nonfinite coordinates')
    return result


def checked_matrix(matrix):
    h = finite_vector(matrix, 9, 'homography')
    determinant = (h[0]*(h[4]*h[8]-h[5]*h[7])-
                   h[1]*(h[3]*h[8]-h[5]*h[6])+h[2]*(h[3]*h[7]-h[4]*h[6]))
    scale = max(abs(v) for v in h)
    if not scale or abs(determinant) <= 1e-12*scale**3:
        raise ValueError('degenerate homography')
    return h


class CoordinateMapper:
    def __init__(self, *, camera_id, transform_id, width, height,
                 pixel_to_reference=None, reference_id=None, calibration=None):
        self.camera_id, self.transform_id = camera_id, transform_id
        self.width, self.height = int(width), int(height)
        if not camera_id or not transform_id or self.width <= 0 or self.height <= 0:
            raise ValueError('image-space identity and dimensions required')
        self.pixel_to_reference = checked_matrix(pixel_to_reference or [1,0,0,0,1,0,0,0,1])
        self.reference_id = reference_id or transform_id
        self.calibration = calibration
        self.table_matrix = None
        self.table_bounds = None
        if calibration is not None:
            if calibration.get('coordinate_frame') != 'table_xy_mm':
                raise ValueError('calibration must describe table_xy_mm, not robot base/3D')
            if not calibration.get('calibration_id'):
                raise ValueError('calibration_id required')
            self.table_matrix = checked_matrix(calibration['pixel_to_table_mm'])
            bounds=finite_vector(calibration['table_bounds_mm'], 4, 'table bounds')
            if bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:
                raise ValueError('calibration table bounds are reversed or empty')
            self.table_bounds = bounds

    def map(self, point, identity):
        if (identity.camera_id, identity.transform_id) != (self.camera_id, self.transform_id):
            raise ValueError('pixel identity differs from mapper')
        x, y = finite_vector(point, 2, 'pixel coordinate')
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise ValueError('pixel coordinate outside image')
        reference = homography_point(self.pixel_to_reference, (x, y))
        result = dict(pixel_xy=[x,y], pixel_units='px', pixel_space=self.transform_id,
                      reference_pixel_xy=list(reference), reference_space=self.reference_id,
                      table_xy_mm=None, calibration_id=None, table_reason='no_matching_calibration',
                      **identity.as_dict())
        c = self.calibration
        if c is None:
            return result
        if (c.get('camera_id') != identity.camera_id or
                c.get('transform_id') != identity.transform_id or
                c.get('image_size') != [self.width, self.height]):
            return result
        result['calibration_id'] = c['calibration_id']
        try:
            table = homography_point(self.table_matrix, (x,y))
        except ValueError:
            result['table_reason'] = 'homography_horizon'
            return result
        x0,y0,x1,y1 = self.table_bounds
        if not x0 <= table[0] <= x1 or not y0 <= table[1] <= y1:
            result['table_reason'] = 'outside_calibrated_table'
            return result
        result.update(table_xy_mm=list(table), table_reason=None,
                      table_coordinate_frame='table_xy_mm')
        return result


def import_legacy_normalized_grid(matrix, width, height, board_width_mm, board_height_mm):
    """Convert grid_overlay.js normalized image->normalized board convention.

    Existing gridMm applies u=x/width,v=y/height then scales X by400,Y by300.
    Dimensions here must come from the matching physical board/calibration.
    This conversion alone does not bind or validate a camera calibration.
    """
    h = checked_matrix(matrix)
    if min(width,height,board_width_mm,board_height_mm) <= 0:
        raise ValueError('positive image and physical board dimensions required')
    return checked_matrix([board_width_mm*h[0]/width, board_width_mm*h[1]/height, board_width_mm*h[2],
                           board_height_mm*h[3]/width, board_height_mm*h[4]/height, board_height_mm*h[5],
                           h[6]/width, h[7]/height, h[8]])


def color_centroid(stats):
    count = stats['count']
    if type(count) is not int or count < 0:
        raise ValueError('invalid pixel count')
    if not count:
        return dict(valid=False, pixel_xy=None, kind='color_matching_pixel_centroid', reason='empty_mask')
    x0,y0,x1,y1 = stats['bbox']
    sx,sy = stats['sum_x'],stats['sum_y']
    if (not all(type(v) is int for v in (sx,sy,x0,y0,x1,y1)) or
            not count*x0 <= sx <= count*x1 or not count*y0 <= sy <= count*y1):
        raise ValueError('moments inconsistent with count/bbox')
    return dict(valid=True, pixel_xy=[sx/count,sy/count], kind='color_matching_pixel_centroid', reason=None)


def associate_color(detections, stats, identity):
    """Conservative one semantic object + one PL mask component policy.

    A global same-color box can merge objects. Require the actual returned PL
    mask to have exactly one 8-connected component and lie wholly inside the
    sole semantic box. This does not infer a garbage class from a color.
    """
    for key, expected in identity.as_dict().items():
        if stats.get(key) != expected or any(d.get(key) != expected for d in detections):
            return dict(state='indeterminate', reason='source_identity_mismatch')
    if len(detections) != 1:
        return dict(state='indeterminate', reason='semantic_target_not_unique')
    if not stats.get('count'):
        return dict(state='not_applicable', reason='empty_color_mask')
    if stats.get('mask') is None:
        return dict(state='indeterminate', reason='mask_components_unavailable')
    import cv2
    import numpy as np
    mask = np.ascontiguousarray(stats['mask'], dtype=np.uint8)
    if mask.ndim != 2 or int(np.count_nonzero(mask)) != stats['count']:
        return dict(state='indeterminate', reason='mask_statistics_mismatch')
    components, _, component_stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if components != 2:
        return dict(state='indeterminate', reason='multiple_color_regions')
    x,y,w,h,area = (int(v) for v in component_stats[1])
    if [x,y,x+w-1,y+h-1] != list(stats['bbox']) or area != stats['count']:
        return dict(state='indeterminate', reason='component_bbox_mismatch')
    x0,y0,x1,y1 = detections[0]['bbox']
    if not (x0 <= x and y0 <= y and x+w-1 <= x1 and y+h-1 <= y1):
        return dict(state='indeterminate', reason='color_region_not_inside_semantic_box')
    return dict(state='associated', reason=None, detection_index=0, components=1)

import math

from utils.models.annotation import OBBCoordinates


def calculate_obb_from_canvas(
    left: float,
    top: float,
    width: float,
    height: float,
    angle: float,
    scale_x: float,
    scale_y: float,
    canvas_width: int,
    canvas_height: int,
) -> OBBCoordinates:
    """
    Calculate OBB corner coordinates from Fabric.js canvas object properties.

    Fabric.js provides:
    - left, top: position of the object's center (after transformations)
    - width, height: original dimensions before scaling
    - angle: rotation in degrees (clockwise)
    - scaleX, scaleY: scale factors

    Returns normalized coordinates (0-1) for YOLO OBB format.
    The corners are ordered counter-clockwise starting from top-left:
    top-left, bottom-left, bottom-right, top-right (when angle=0).
    """
    # Apply scaling to get actual dimensions
    actual_width = width * scale_x
    actual_height = height * scale_y

    # Half dimensions for corner calculation
    half_w = actual_width / 2
    half_h = actual_height / 2

    # Convert angle to radians (Fabric.js uses clockwise degrees)
    angle_rad = math.radians(angle)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Calculate center position
    # In Fabric.js, left/top is the position of the object's bounding box corner
    # but after rotation, we need to find the center
    center_x = left + half_w * cos_a - half_h * sin_a
    center_y = top + half_w * sin_a + half_h * cos_a

    # Define corners relative to center (before rotation)
    # Order: counter-clockwise starting from top-left (YOLO OBB format)
    # See: https://github.com/ultralytics/ultralytics/issues/19428
    corners_local = [
        (-half_w, -half_h),  # top-left
        (-half_w, half_h),  # bottom-left
        (half_w, half_h),  # bottom-right
        (half_w, -half_h),  # top-right
    ]

    # Rotate and translate corners
    corners = []
    for lx, ly in corners_local:
        # Rotate around center
        rx = lx * cos_a - ly * sin_a
        ry = lx * sin_a + ly * cos_a
        # Translate to canvas position
        x = center_x + rx
        y = center_y + ry
        corners.append((x, y))

    # Normalize to 0-1 range
    normalized = []
    for x, y in corners:
        nx = max(0.0, min(1.0, x / canvas_width))
        ny = max(0.0, min(1.0, y / canvas_height))
        normalized.append((nx, ny))

    return OBBCoordinates(
        x1=normalized[0][0],
        y1=normalized[0][1],
        x2=normalized[1][0],
        y2=normalized[1][1],
        x3=normalized[2][0],
        y3=normalized[2][1],
        x4=normalized[3][0],
        y4=normalized[3][1],
    )


def calculate_obb_from_fabric_object(
    obj: dict,
    canvas_width: int,
    canvas_height: int,
) -> OBBCoordinates:
    """
    Calculate OBB from a Fabric.js object dictionary.

    This is a convenience wrapper that extracts the relevant properties
    from the canvas JSON data.
    """
    return calculate_obb_from_canvas(
        left=obj.get("left", 0),
        top=obj.get("top", 0),
        width=obj.get("width", 0),
        height=obj.get("height", 0),
        angle=obj.get("angle", 0),
        scale_x=obj.get("scaleX", 1),
        scale_y=obj.get("scaleY", 1),
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )

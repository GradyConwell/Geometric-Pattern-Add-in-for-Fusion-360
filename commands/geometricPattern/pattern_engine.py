import math
from typing import List, Tuple, Optional, Dict, Any

# Data structures representing computed pattern items
class PatternItem:
    def __init__(self, u: float, v: float, size: float, shape_type: str = 'circle'):
        self.u = u
        self.v = v
        self.size = size  # Diameter / primary dimension in cm
        self.radius = size / 2.0
        self.shape_type = shape_type
        self.world_center = None  # (x, y, z) in cm


class FaceCoordinateFrame:
    """Represents an orthonormal 2D UV coordinate system on a 3D planar face."""
    def __init__(self, origin: Tuple[float, float, float], u_dir: Tuple[float, float, float], v_dir: Tuple[float, float, float], normal: Tuple[float, float, float]):
        self.origin = origin
        self.u_dir = self._normalize(u_dir)
        self.v_dir = self._normalize(v_dir)
        self.normal = self._normalize(normal)

    @staticmethod
    def _normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        mag = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
        if mag < 1e-9:
            return (0.0, 0.0, 1.0)
        return (v[0]/mag, v[1]/mag, v[2]/mag)

    def to_uv(self, pt3d: Tuple[float, float, float]) -> Tuple[float, float]:
        dx = pt3d[0] - self.origin[0]
        dy = pt3d[1] - self.origin[1]
        dz = pt3d[2] - self.origin[2]
        u = dx * self.u_dir[0] + dy * self.u_dir[1] + dz * self.u_dir[2]
        v = dx * self.v_dir[0] + dy * self.v_dir[1] + dz * self.v_dir[2]
        return (u, v)

    def to_3d(self, u: float, v: float) -> Tuple[float, float, float]:
        x = self.origin[0] + u * self.u_dir[0] + v * self.v_dir[0]
        y = self.origin[1] + u * self.u_dir[1] + v * self.v_dir[1]
        z = self.origin[2] + u * self.u_dir[2] + v * self.v_dir[2]
        return (x, y, z)


def compute_spread_factor(d: float, spread: float) -> float:
    """
    Computes non-linear interpolation factor t in [0, 1] for normalized distance d in [0, 1]
    given spread factor in [-1.0, 1.0].
    spread = 0: linear transition
    spread < 0: decays faster towards size 2 (smaller pattern region)
    spread > 0: sustains size 1 larger across most of the area
    """
    d_clamped = max(0.0, min(1.0, d))
    if abs(spread) < 1e-4:
        return d_clamped
    
    # Power curve mapping: gamma = 2^(-spread * 3.0)
    # When spread = -0.6: gamma ~ 3.48 -> t = d^3.48
    # When spread = +0.6: gamma ~ 0.287 -> t = d^0.287
    gamma = math.pow(2.0, -spread * 3.0)
    return math.pow(d_clamped, gamma)


def compute_item_size(d: float, size_limit_1: float, size_limit_2: float, spread: float) -> float:
    """Calculates interpolated diameter between size_limit_1 and size_limit_2."""
    t = compute_spread_factor(d, spread)
    return size_limit_1 * (1.0 - t) + size_limit_2 * t


def is_point_in_polygon(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Computes minimum Euclidean distance from point (px, py) to segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx*dx + dy*dy
    if l2 < 1e-12:
        return math.hypot(px - x1, py - y1)
    
    # Projection parameter t on segment
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def min_distance_to_polygon(px: float, py: float, poly: List[Tuple[float, float]]) -> float:
    """Computes minimum distance from point to all boundary edges of polygon."""
    n = len(poly)
    if n < 2:
        return float('inf')
    min_d = float('inf')
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        d = point_to_segment_distance(px, py, p1[0], p1[1], p2[0], p2[1])
        if d < min_d:
            min_d = d
    return min_d


def generate_geometric_pattern(
    outer_poly: List[Tuple[float, float]],
    inner_polys: List[List[Tuple[float, float]]],
    distribution_type: str = 'TRIANGULAR',  # 'TRIANGULAR', 'RECTANGULAR', 'HEXAGONAL', 'RADIAL'
    object_type: str = 'CIRCLE',            # 'CIRCLE', 'CYLINDER', 'BOX', 'CUSTOM'
    size_limit_1: float = 0.60,             # cm (6.0 mm)
    size_limit_2: float = 0.20,             # cm (2.0 mm)
    spread: float = -0.60,
    distance: float = 1.48,                 # cm (14.8 mm spacing)
    u_alignment: str = 'CENTER',            # 'LEFT', 'CENTER', 'RIGHT'
    v_alignment: str = 'CENTER',            # 'BOTTOM', 'CENTER', 'TOP'
    clear_perimeter: bool = True,
    perimeter_margin: float = 0.05,         # cm (0.5 mm extra clearance)
    gradient_axis: str = 'RADIAL',          # 'RADIAL', 'U_AXIS', 'V_AXIS'
    max_items: int = 1500                   # Safety cap to ensure responsive performance
) -> List[PatternItem]:
    """
    Generates a list of valid PatternItems distributed across the face polygon.
    """
    if len(outer_poly) < 3 or distance <= 0.01:
        return []

    # 1. Compute 2D bounding box
    min_u = min(p[0] for p in outer_poly)
    max_u = max(p[0] for p in outer_poly)
    min_v = min(p[1] for p in outer_poly)
    max_v = max(p[1] for p in outer_poly)

    width = max_u - min_u
    height = max_v - min_v
    if width <= 0.001 or height <= 0.001:
        return []

    center_u = (min_u + max_u) / 2.0
    center_v = (min_v + max_v) / 2.0
    max_radius = max(width, height) / 2.0
    if max_radius < 1e-4:
        max_radius = 1.0

    # 2. Determine grid step and alignment offsets
    dist_type = distribution_type.upper()
    u_align = u_alignment.upper()
    v_align = v_alignment.upper()

    candidates: List[Tuple[float, float]] = []

    if dist_type in ('TRIANGULAR', 'HEXAGONAL', 'DELTA'):
        # Staggered 60° triangular layout (delta pattern)
        pitch_u = distance
        pitch_v = distance * (math.sqrt(3.0) / 2.0)

        # Calculate number of rows and columns needed to cover bounds with margins
        num_cols = int(math.ceil(width / pitch_u)) + 4
        num_rows = int(math.ceil(height / pitch_v)) + 4

        # U Alignment offset
        if u_align == 'LEFT':
            base_u = min_u + pitch_u * 0.5
        elif u_align == 'RIGHT':
            base_u = max_u - (num_cols - 1) * pitch_u
        else:  # CENTER
            base_u = center_u - (num_cols // 2) * pitch_u

        # V Alignment offset
        if v_align == 'BOTTOM':
            base_v = min_v + pitch_v * 0.5
        elif v_align == 'TOP':
            base_v = max_v - (num_rows - 1) * pitch_v
        else:  # CENTER
            base_v = center_v - (num_rows // 2) * pitch_v

        for j in range(-2, num_rows + 2):
            v = base_v + j * pitch_v
            # Row stagger: offset every odd row by 0.5 * pitch_u
            row_stagger = (j % 2) * (pitch_u * 0.5)
            for i in range(-2, num_cols + 2):
                u = base_u + i * pitch_u + row_stagger
                if min_u - distance <= u <= max_u + distance and min_v - distance <= v <= max_v + distance:
                    candidates.append((u, v))

    elif dist_type == 'RADIAL':
        # Concentric radial rings around center
        candidates.append((center_u, center_v))
        num_rings = int(math.ceil(max_radius / distance)) + 1
        for ring in range(1, num_rings + 1):
            r = ring * distance
            circumference = 2.0 * math.pi * r
            num_pts = max(6, int(round(circumference / distance)))
            for k in range(num_pts):
                theta = 2.0 * math.pi * k / num_pts
                u = center_u + r * math.cos(theta)
                v = center_v + r * math.sin(theta)
                if min_u - distance <= u <= max_u + distance and min_v - distance <= v <= max_v + distance:
                    candidates.append((u, v))

    else:  # RECTANGULAR / GRID
        pitch_u = distance
        pitch_v = distance

        num_cols = int(math.ceil(width / pitch_u)) + 4
        num_rows = int(math.ceil(height / pitch_v)) + 4

        if u_align == 'LEFT':
            base_u = min_u + pitch_u * 0.5
        elif u_align == 'RIGHT':
            base_u = max_u - (num_cols - 1) * pitch_u
        else:  # CENTER
            base_u = center_u - (num_cols // 2) * pitch_u

        if v_align == 'BOTTOM':
            base_v = min_v + pitch_v * 0.5
        elif v_align == 'TOP':
            base_v = max_v - (num_rows - 1) * pitch_v
        else:  # CENTER
            base_v = center_v - (num_rows // 2) * pitch_v

        for j in range(-2, num_rows + 2):
            v = base_v + j * pitch_v
            for i in range(-2, num_cols + 2):
                u = base_u + i * pitch_u
                if min_u - distance <= u <= max_u + distance and min_v - distance <= v <= max_v + distance:
                    candidates.append((u, v))

    # 3. Filter candidates and calculate size gradient for each item
    items: List[PatternItem] = []

    for u, v in candidates:
        if len(items) >= max_items:
            break

        # Check if inside outer boundary
        if not is_point_in_polygon(u, v, outer_poly):
            continue

        # Check if outside all inner hole boundaries
        in_hole = False
        for hole in inner_polys:
            if is_point_in_polygon(u, v, hole):
                in_hole = True
                break
        if in_hole:
            continue

        # Calculate normalized distance for size gradient
        if gradient_axis == 'U_AXIS':
            norm_d = abs(u - center_u) / (width / 2.0 if width > 0 else 1.0)
        elif gradient_axis == 'V_AXIS':
            norm_d = abs(v - center_v) / (height / 2.0 if height > 0 else 1.0)
        else:  # RADIAL / CENTER
            # Elliptical normalized distance to face bounds
            du = (u - center_u) / (width / 2.0 if width > 0 else 1.0)
            dv = (v - center_v) / (height / 2.0 if height > 0 else 1.0)
            norm_d = math.sqrt(du*du + dv*dv)

        item_size = compute_item_size(norm_d, size_limit_1, size_limit_2, spread)
        item_radius = item_size / 2.0

        # Perimeter clearance check
        if clear_perimeter:
            min_edge_dist = min_distance_to_polygon(u, v, outer_poly)
            for hole in inner_polys:
                hole_dist = min_distance_to_polygon(u, v, hole)
                if hole_dist < min_edge_dist:
                    min_edge_dist = hole_dist

            required_clearance = item_radius + perimeter_margin
            if min_edge_dist < required_clearance:
                continue

        item = PatternItem(u, v, item_size, shape_type=object_type.lower())
        items.append(item)

    return items

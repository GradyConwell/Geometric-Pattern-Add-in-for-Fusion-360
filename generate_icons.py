import os
import math
import struct
import zlib

BASE_RES = "/Users/gradyconwell/Documents/CS Projects/Fusion 360 Custom Geometric Pattern Add In/commands/geometricPattern/resources"

class Canvas:
    """A supersampled 2D RGBA drawing canvas in pure Python with anti-aliasing."""
    def __init__(self, base_size=64, supersample=4):
        self.base_size = base_size
        self.ss = supersample
        self.width = base_size * supersample
        self.height = base_size * supersample
        # Buffer of RGBA tuples
        self.pixels = [[(0, 0, 0, 0) for _ in range(self.width)] for _ in range(self.height)]

    def set_pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            sr, sg, sb, sa = color
            if sa == 0:
                return
            dr, dg, db, da = self.pixels[y][x]
            if da == 0 or sa == 255:
                self.pixels[y][x] = color
            else:
                a_norm = sa / 255.0
                out_r = int(sr * a_norm + dr * (1.0 - a_norm))
                out_g = int(sg * a_norm + dg * (1.0 - a_norm))
                out_b = int(sb * a_norm + db * (1.0 - a_norm))
                out_a = min(255, int(sa + da * (1.0 - a_norm)))
                self.pixels[y][x] = (out_r, out_g, out_b, out_a)

    def draw_circle(self, cx, cy, r, fill_color=None, stroke_color=None, stroke_width=2.0):
        scale = (self.base_size / 32.0) * self.ss
        scx = cx * scale
        scy = cy * scale
        sr = r * scale
        sw = (stroke_width * scale) / 2.0

        min_x = max(0, int(scx - sr - sw - 2))
        max_x = min(self.width, int(scx + sr + sw + 3))
        min_y = max(0, int(scy - sr - sw - 2))
        max_y = min(self.height, int(scy + sr + sw + 3))

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                d = math.hypot(x - scx, y - scy)
                if fill_color and d <= sr:
                    self.set_pixel(x, y, fill_color)
                if stroke_color and abs(d - sr) <= sw:
                    self.set_pixel(x, y, stroke_color)

    def draw_ellipse(self, cx, cy, rx, ry, fill_color=None, stroke_color=None, stroke_width=2.0):
        scale = (self.base_size / 32.0) * self.ss
        scx = cx * scale
        scy = cy * scale
        srx = rx * scale
        sry = ry * scale
        sw = (stroke_width * scale) / 2.0

        min_x = max(0, int(scx - srx - sw - 2))
        max_x = min(self.width, int(scx + srx + sw + 3))
        min_y = max(0, int(scy - sry - sw - 2))
        max_y = min(self.height, int(scy + sry + sw + 3))

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                val = ((x - scx) / (srx if srx > 0 else 1))**2 + ((y - scy) / (sry if sry > 0 else 1))**2
                if fill_color and val <= 1.0:
                    self.set_pixel(x, y, fill_color)
                if stroke_color and abs(val - 1.0) <= (sw / max(srx, sry)):
                    self.set_pixel(x, y, stroke_color)

    def draw_line(self, x1, y1, x2, y2, color, stroke_width=2.0):
        scale = (self.base_size / 32.0) * self.ss
        sx1, sy1 = x1 * scale, y1 * scale
        sx2, sy2 = x2 * scale, y2 * scale
        sw = (stroke_width * scale) / 2.0

        length = math.hypot(sx2 - sx1, sy2 - sy1)
        if length < 1e-4:
            return

        steps = int(math.ceil(length * 2))
        for step in range(steps + 1):
            t = step / float(steps)
            px = sx1 + t * (sx2 - sx1)
            py = sy1 + t * (sy2 - sy1)

            min_x = max(0, int(px - sw - 1))
            max_x = min(self.width, int(px + sw + 2))
            min_y = max(0, int(py - sw - 1))
            max_y = min(self.height, int(py + sw + 2))

            for y in range(min_y, max_y):
                for x in range(min_x, max_x):
                    if math.hypot(x - px, y - py) <= sw:
                        self.set_pixel(x, y, color)

    def draw_polygon(self, pts, fill_color=None, stroke_color=None, stroke_width=2.0):
        scale = (self.base_size / 32.0) * self.ss
        spts = [(p[0] * scale, p[1] * scale) for p in pts]
        n = len(spts)
        if n < 3:
            return

        if fill_color:
            min_x = max(0, int(min(p[0] for p in spts)))
            max_x = min(self.width, int(max(p[0] for p in spts) + 1))
            min_y = max(0, int(min(p[1] for p in spts)))
            max_y = min(self.height, int(max(p[1] for p in spts) + 1))

            for y in range(min_y, max_y):
                for x in range(min_x, max_x):
                    inside = False
                    p1x, p1y = spts[0]
                    for i in range(1, n + 1):
                        p2x, p2y = spts[i % n]
                        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                            if p1y != p2y:
                                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or x <= xinters:
                                inside = not inside
                        p1x, p1y = p2x, p2y
                    if inside:
                        self.set_pixel(x, y, fill_color)

        if stroke_color:
            for i in range(n):
                p1 = pts[i]
                p2 = pts[(i + 1) % n]
                self.draw_line(p1[0], p1[1], p2[0], p2[1], stroke_color, stroke_width)

    def to_png(self, final_size):
        """Downsamples supersampled buffer with anti-aliasing and returns PNG bytes."""
        ratio = self.width // final_size
        raw_data = bytearray()

        for fy in range(final_size):
            raw_data.append(0) # Filter None
            sy_start = fy * ratio
            sy_end = sy_start + ratio
            for fx in range(final_size):
                sx_start = fx * ratio
                sx_end = sx_start + ratio

                sum_r, sum_g, sum_b, sum_a = 0, 0, 0, 0
                count = 0
                for y in range(sy_start, min(self.height, sy_end)):
                    for x in range(sx_start, min(self.width, sx_end)):
                        r, g, b, a = self.pixels[y][x]
                        sum_r += r * (a / 255.0)
                        sum_g += g * (a / 255.0)
                        sum_b += b * (a / 255.0)
                        sum_a += a
                        count += 1

                if count > 0:
                    avg_a = sum_a / float(count)
                    if avg_a > 0:
                        avg_r = (sum_r / float(count)) / (avg_a / 255.0)
                        avg_g = (sum_g / float(count)) / (avg_a / 255.0)
                        avg_b = (sum_b / float(count)) / (avg_a / 255.0)
                        raw_data.extend([int(avg_r), int(avg_g), int(avg_b), int(avg_a)])
                    else:
                        raw_data.extend([0, 0, 0, 0])
                else:
                    raw_data.extend([0, 0, 0, 0])

        png = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', final_size, final_size, 8, 6, 0, 0, 0)
        png += struct.pack('>I', len(ihdr)) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr))

        compressed = zlib.compress(bytes(raw_data))
        png += struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', zlib.crc32(b'IDAT' + compressed))

        png += struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND'))
        return png


def render_icon(name: str, is_dark: bool = False, is_disabled: bool = False) -> Canvas:
    c = Canvas(base_size=64, supersample=4)

    if is_disabled:
        stroke = (148, 163, 184, 180)
        fill = (203, 213, 225, 120)
        accent = (148, 163, 184, 200)
    elif is_dark:
        stroke = (226, 232, 240, 255)
        fill = (56, 189, 248, 180)
        accent = (56, 189, 248, 255)
    else:
        stroke = (30, 41, 59, 255)
        fill = (14, 165, 233, 200)
        accent = (2, 132, 199, 255)

    if name == 'type_circle':
        c.draw_circle(16, 16, 10, fill_color=fill, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(13, 13, 3, fill_color=(255, 255, 255, 180))

    elif name == 'type_cylinder':
        c.draw_ellipse(16, 21, 9, 4.5, fill_color=fill, stroke_color=stroke, stroke_width=2.0)
        body_pts = [(7, 11), (25, 11), (25, 21), (7, 21)]
        c.draw_polygon(body_pts, fill_color=fill)
        c.draw_line(7, 11, 7, 21, stroke, stroke_width=2.0)
        c.draw_line(25, 11, 25, 21, stroke, stroke_width=2.0)
        c.draw_ellipse(16, 11, 9, 4.5, fill_color=fill, stroke_color=stroke, stroke_width=2.0)

    elif name == 'type_box':
        top_pts = [(16, 6), (25, 11), (16, 16), (7, 11)]
        left_pts = [(7, 11), (16, 16), (16, 25), (7, 20)]
        right_pts = [(16, 16), (25, 11), (25, 20), (16, 25)]

        c.draw_polygon(top_pts, fill_color=fill, stroke_color=stroke, stroke_width=2.0)
        c.draw_polygon(left_pts, fill_color=(fill[0], fill[1], fill[2], max(0, fill[3] - 40)), stroke_color=stroke, stroke_width=2.0)
        c.draw_polygon(right_pts, fill_color=(fill[0], fill[1], fill[2], max(0, fill[3] - 80)), stroke_color=stroke, stroke_width=2.0)

    elif name == 'type_hex':
        hex_pts = []
        for k in range(6):
            ang = k * (math.pi / 3.0) - (math.pi / 6.0)
            hex_pts.append((16 + 10 * math.cos(ang), 16 + 10 * math.sin(ang)))
        c.draw_polygon(hex_pts, fill_color=fill, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(16, 16, 3.5, stroke_color=stroke, stroke_width=2.0)

    elif name == 'dist_triangular':
        tri_pts = [(16, 6), (26, 24), (6, 24)]
        c.draw_polygon(tri_pts, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(16, 18, 2.5, fill_color=accent)
        c.draw_circle(16, 6, 2.0, fill_color=accent)
        c.draw_circle(26, 24, 2.0, fill_color=accent)
        c.draw_circle(6, 24, 2.0, fill_color=accent)

    elif name == 'dist_grid':
        sq_pts = [(7, 7), (25, 7), (25, 25), (7, 25)]
        c.draw_polygon(sq_pts, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(7, 7, 2.5, fill_color=accent)
        c.draw_circle(25, 7, 2.5, fill_color=accent)
        c.draw_circle(25, 25, 2.5, fill_color=accent)
        c.draw_circle(7, 25, 2.5, fill_color=accent)

    elif name == 'dist_hex':
        hex_pts = []
        for k in range(6):
            ang = k * (math.pi / 3.0)
            hex_pts.append((16 + 9 * math.cos(ang), 16 + 9 * math.sin(ang)))
        c.draw_polygon(hex_pts, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(16, 16, 2.5, fill_color=accent)

    elif name == 'dist_radial':
        c.draw_circle(16, 16, 10, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(16, 16, 5.5, stroke_color=stroke, stroke_width=2.0)
        c.draw_circle(16, 16, 2.0, fill_color=accent)

    elif name == 'u_left':
        c.draw_line(6, 6, 6, 26, stroke, stroke_width=3.0)
        c.draw_line(6, 10, 22, 10, accent, stroke_width=2.2)
        c.draw_line(6, 16, 16, 16, accent, stroke_width=2.2)
        c.draw_line(6, 22, 24, 22, accent, stroke_width=2.2)

    elif name == 'u_center':
        c.draw_line(16, 6, 16, 26, stroke, stroke_width=3.0)
        c.draw_line(8, 10, 24, 10, accent, stroke_width=2.2)
        c.draw_line(11, 16, 21, 16, accent, stroke_width=2.2)
        c.draw_line(7, 22, 25, 22, accent, stroke_width=2.2)

    elif name == 'u_right':
        c.draw_line(26, 6, 26, 26, stroke, stroke_width=3.0)
        c.draw_line(10, 10, 26, 10, accent, stroke_width=2.2)
        c.draw_line(16, 16, 26, 16, accent, stroke_width=2.2)
        c.draw_line(8, 22, 26, 22, accent, stroke_width=2.2)

    elif name == 'v_bottom':
        c.draw_line(6, 26, 26, 26, stroke, stroke_width=3.0)
        c.draw_line(10, 10, 10, 26, accent, stroke_width=2.2)
        c.draw_line(16, 16, 16, 26, accent, stroke_width=2.2)
        c.draw_line(22, 8, 22, 26, accent, stroke_width=2.2)

    elif name == 'v_center':
        c.draw_line(6, 16, 26, 16, stroke, stroke_width=3.0)
        c.draw_line(10, 8, 10, 24, accent, stroke_width=2.2)
        c.draw_line(16, 11, 16, 21, accent, stroke_width=2.2)
        c.draw_line(22, 7, 22, 25, accent, stroke_width=2.2)

    elif name == 'v_top':
        c.draw_line(6, 6, 26, 6, stroke, stroke_width=3.0)
        c.draw_line(10, 6, 10, 22, accent, stroke_width=2.2)
        c.draw_line(16, 6, 16, 16, accent, stroke_width=2.2)
        c.draw_line(22, 6, 22, 24, accent, stroke_width=2.2)

    return c


icon_names = [
    'type_circle', 'type_cylinder', 'type_box', 'type_hex',
    'dist_triangular', 'dist_grid', 'dist_hex', 'dist_radial',
    'u_left', 'u_center', 'u_right',
    'v_bottom', 'v_center', 'v_top'
]

for name in icon_names:
    folder = os.path.join(BASE_RES, name)
    os.makedirs(folder, exist_ok=True)

    c_light = render_icon(name, is_dark=False, is_disabled=False)
    c_dark = render_icon(name, is_dark=True, is_disabled=False)
    c_dis = render_icon(name, is_dark=False, is_disabled=True)

    with open(os.path.join(folder, "16x16.png"), "wb") as f:
        f.write(c_light.to_png(16))
    with open(os.path.join(folder, "16x16@2x.png"), "wb") as f:
        f.write(c_light.to_png(32))
    with open(os.path.join(folder, "16x16-dark.png"), "wb") as f:
        f.write(c_dark.to_png(16))
    with open(os.path.join(folder, "16x16-dark@2x.png"), "wb") as f:
        f.write(c_dark.to_png(32))
    with open(os.path.join(folder, "16x16-disabled.png"), "wb") as f:
        f.write(c_dis.to_png(16))

    with open(os.path.join(folder, "32x32.png"), "wb") as f:
        f.write(c_light.to_png(32))
    with open(os.path.join(folder, "32x32@2x.png"), "wb") as f:
        f.write(c_light.to_png(64))
    with open(os.path.join(folder, "32x32-dark.png"), "wb") as f:
        f.write(c_dark.to_png(32))
    with open(os.path.join(folder, "32x32-dark@2x.png"), "wb") as f:
        f.write(c_dark.to_png(64))
    with open(os.path.join(folder, "32x32-disabled.png"), "wb") as f:
        f.write(c_dis.to_png(32))

print("Regenerated all icons cleanly!")

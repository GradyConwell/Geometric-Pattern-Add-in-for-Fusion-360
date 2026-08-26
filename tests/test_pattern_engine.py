import unittest
import math
import sys
import os
import importlib.util

# Load pattern_engine directly without triggering adsk imports in entry.py
engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'commands', 'geometricPattern', 'pattern_engine.py'))
spec = importlib.util.spec_from_file_location("pattern_engine", engine_path)
pattern_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern_engine)

compute_spread_factor = pattern_engine.compute_spread_factor
compute_item_size = pattern_engine.compute_item_size
is_point_in_polygon = pattern_engine.is_point_in_polygon
point_to_segment_distance = pattern_engine.point_to_segment_distance
min_distance_to_polygon = pattern_engine.min_distance_to_polygon
generate_geometric_pattern = pattern_engine.generate_geometric_pattern
FaceCoordinateFrame = pattern_engine.FaceCoordinateFrame


class TestPatternEngine(unittest.TestCase):
    def test_spread_factor(self):
        # When d = 0 (center), t should be 0
        self.assertAlmostEqual(compute_spread_factor(0.0, 0.0), 0.0)
        self.assertAlmostEqual(compute_spread_factor(0.0, -0.6), 0.0)
        self.assertAlmostEqual(compute_spread_factor(0.0, 0.6), 0.0)

        # When d = 1 (edge), t should be 1
        self.assertAlmostEqual(compute_spread_factor(1.0, 0.0), 1.0)
        self.assertAlmostEqual(compute_spread_factor(1.0, -0.6), 1.0)
        self.assertAlmostEqual(compute_spread_factor(1.0, 0.6), 1.0)

        # For d = 0.5:
        # spread = 0 -> t = 0.5
        self.assertAlmostEqual(compute_spread_factor(0.5, 0.0), 0.5)
        # spread = -0.6 (negative spread -> gamma > 1 -> 0.5^gamma < 0.5)
        t_neg = compute_spread_factor(0.5, -0.6)
        self.assertLess(t_neg, 0.5)

    def test_point_in_polygon(self):
        # Unit square [0, 10] x [0, 10]
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        self.assertTrue(is_point_in_polygon(5.0, 5.0, square))
        self.assertTrue(is_point_in_polygon(1.0, 1.0, square))
        self.assertFalse(is_point_in_polygon(11.0, 5.0, square))
        self.assertFalse(is_point_in_polygon(-1.0, 5.0, square))

    def test_min_distance_to_polygon(self):
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        # Center (5, 5) distance to edge should be 5.0
        self.assertAlmostEqual(min_distance_to_polygon(5.0, 5.0, square), 5.0)
        # Point (1, 5) distance to left edge should be 1.0
        self.assertAlmostEqual(min_distance_to_polygon(1.0, 5.0, square), 1.0)

    def test_triangular_pattern_generation(self):
        # A rectangular face of 20 x 10 cm
        poly = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
        items = generate_geometric_pattern(
            outer_poly=poly,
            inner_polys=[],
            distribution_type='TRIANGULAR',
            size_limit_1=0.6,
            size_limit_2=0.2,
            spread=-0.6,
            distance=1.5,
            clear_perimeter=True,
            perimeter_margin=0.1
        )
        self.assertGreater(len(items), 10)
        for item in items:
            # Check all items are within boundary with perimeter clearance
            self.assertGreaterEqual(item.u - item.radius, 0.0)
            self.assertLessEqual(item.u + item.radius, 20.0)
            self.assertGreaterEqual(item.v - item.radius, 0.0)
            self.assertLessEqual(item.v + item.radius, 10.0)
            # Check size is between limits
            self.assertGreaterEqual(item.size, 0.19)
            self.assertLessEqual(item.size, 0.61)

    def test_radial_pattern_generation(self):
        poly = [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]
        items = generate_geometric_pattern(
            outer_poly=poly,
            inner_polys=[],
            distribution_type='RADIAL',
            size_limit_1=0.8,
            size_limit_2=0.3,
            spread=0.0,
            distance=2.0,
            clear_perimeter=True,
            perimeter_margin=0.2
        )
        self.assertGreater(len(items), 5)

    def test_face_coordinate_frame(self):
        frame = FaceCoordinateFrame(
            origin=(0, 0, 0),
            u_dir=(1, 0, 0),
            v_dir=(0, 1, 0),
            normal=(0, 0, 1)
        )
        pt3d = (3.0, 4.0, 0.0)
        u, v = frame.to_uv(pt3d)
        self.assertAlmostEqual(u, 3.0)
        self.assertAlmostEqual(v, 4.0)
        reconstructed = frame.to_3d(u, v)
        self.assertAlmostEqual(reconstructed[0], 3.0)
        self.assertAlmostEqual(reconstructed[1], 4.0)
        self.assertAlmostEqual(reconstructed[2], 0.0)


if __name__ == '__main__':
    unittest.main()

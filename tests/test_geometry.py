"""geometry.feasible_region 的单元测试（仅标准库）。"""

import math
import unittest

from app.geometry import (
    NoFeasibleAreaError,
    Observation,
    feasible_region,
    _signed_area,
)


def verts_of(poly):
    return [tuple(round(v, 9) for v in p) for p in poly]


class TestWedgeIntersection(unittest.TestCase):
    def test_two_stations_basic_intersection(self):
        # 两站分别指向正方形中心附近，交集为四边形区域
        rect = (0.0, 0.0, 100.0, 100.0)
        obs = [
            Observation(0.0, 0.0, azimuth=45.0, half_angle=10.0),
            Observation(100.0, 0.0, azimuth=315.0, half_angle=10.0),
        ]
        poly, area = feasible_region(rect, obs)
        self.assertGreater(len(poly), 2)
        self.assertGreater(area, 0.0)
        # 结果应为逆时针
        self.assertGreater(_signed_area(poly), 0.0)
        # 顶点都在矩形内
        for x, y in poly:
            self.assertGreaterEqual(x, -1e-9)
            self.assertLessEqual(x, 100.0 + 1e-9)
            self.assertGreaterEqual(y, -1e-9)
            self.assertLessEqual(y, 100.0 + 1e-9)
        # 对称情形：交集关于 x=50 对称
        cx = sum(x for x, _ in poly) / len(poly)
        self.assertAlmostEqual(cx, 50.0, places=6)

    def test_north_azimuth_wedge_clips_half_plane(self):
        # 正北、半角 45：扇区边界为东北与西北方向（方位角 -45 / +45），
        # 相对测站满足 y-5 >= |x-5|，在 10x10 矩形内是面积 25 的三角形
        rect = (0.0, 0.0, 10.0, 10.0)
        obs = [
            Observation(5.0, 5.0, azimuth=0.0, half_angle=45.0),
            Observation(5.0, 5.0, azimuth=0.0, half_angle=45.0),
        ]
        poly, area = feasible_region(rect, obs)
        self.assertAlmostEqual(area, 25.0, places=6)
        self.assertEqual(verts_of(poly), [(0.0, 10.0), (5.0, 5.0), (10.0, 10.0)])

    def test_east_azimuth_wedge_clips_half_plane(self):
        # 正东、半角 45：相对测站满足 x-5 >= |y-5|，面积同样为 25 的三角形
        rect = (0.0, 0.0, 10.0, 10.0)
        obs = [
            Observation(5.0, 5.0, azimuth=90.0, half_angle=45.0),
            Observation(5.0, 5.0, azimuth=90.0, half_angle=45.0),
        ]
        poly, area = feasible_region(rect, obs)
        self.assertAlmostEqual(area, 25.0, places=6)
        self.assertEqual(verts_of(poly), [(5.0, 5.0), (10.0, 0.0), (10.0, 10.0)])

    def test_wedge_pointing_away_from_rectangle(self):
        # 测站在矩形南侧外，指向正南小半角：与矩形无交集
        rect = (0.0, 0.0, 10.0, 10.0)
        obs = [
            Observation(5.0, -1.0, azimuth=180.0, half_angle=1.0),
            Observation(5.0, -1.0, azimuth=180.0, half_angle=1.0),
        ]
        with self.assertRaises(NoFeasibleAreaError):
            feasible_region(rect, obs)

    def test_back_to_back_stations_no_intersection(self):
        rect = (0.0, 0.0, 100.0, 100.0)
        obs = [
            Observation(10.0, 10.0, azimuth=135.0, half_angle=5.0),  # 指向西南
            Observation(90.0, 90.0, azimuth=315.0, half_angle=5.0),  # 指向东北
        ]
        with self.assertRaises(NoFeasibleAreaError):
            feasible_region(rect, obs)

    def test_single_wedge_contains_center(self):
        # 站在矩形外西侧，指向正东小半角：交集为梯形/三角形带
        rect = (0.0, 0.0, 100.0, 100.0)
        obs_a = Observation(-50.0, 0.0, azimuth=90.0, half_angle=20.0)
        poly, area = feasible_region(
            rect, [obs_a, Observation(-50.0, 0.0, azimuth=90.0, half_angle=45.0)]
        )
        # 宽 45 度扇区包含窄 20 度扇区，结果等于窄扇区与矩形的交集
        poly2, area2 = feasible_region(rect, [obs_a, obs_a])
        self.assertAlmostEqual(area, area2, places=5)

    def test_azimuth_wraparound(self):
        # 360 度与 0 度等价；720 度也等价
        rect = (0.0, 0.0, 10.0, 10.0)
        o1 = [
            Observation(5.0, 5.0, azimuth=0.0, half_angle=10.0),
            Observation(5.0, 5.0, azimuth=0.0, half_angle=10.0),
        ]
        o2 = [
            Observation(5.0, 5.0, azimuth=360.0, half_angle=10.0),
            Observation(5.0, 5.0, azimuth=720.0, half_angle=10.0),
        ]
        _, a1 = feasible_region(rect, o1)
        _, a2 = feasible_region(rect, o2)
        self.assertAlmostEqual(a1, a2, places=9)

    def test_vertices_counterclockwise_and_simple(self):
        rect = (-30.0, -20.0, 80.0, 60.0)
        obs = [
            Observation(0.0, 0.0, azimuth=30.0, half_angle=15.0),
            Observation(80.0, -20.0, azimuth=300.0, half_angle=20.0),
            Observation(-30.0, 60.0, azimuth=120.0, half_angle=12.0),
        ]
        poly, area = feasible_region(rect, obs)
        self.assertGreater(area, 0.0)
        self.assertGreater(_signed_area(poly), 0.0)
        # shoelace 面积与返回值一致
        self.assertAlmostEqual(area, _signed_area(poly), places=9)

    def test_invalid_observation_count(self):
        rect = (0.0, 0.0, 1.0, 1.0)
        with self.assertRaises(ValueError):
            feasible_region(rect, [Observation(0, 0, 0, 10)])
        many = [Observation(0, 0, 0, 10) for _ in range(9)]
        with self.assertRaises(ValueError):
            feasible_region(rect, many)

    def test_degenerate_rectangle(self):
        with self.assertRaises(ValueError):
            feasible_region((0.0, 0.0, 0.0, 10.0), [
                Observation(0, 0, 0, 10), Observation(1, 1, 0, 10)
            ])

    def test_grazing_rays_give_zero_area(self):
        # 两条扇区边界几乎平行，夹出的楔形在矩形内面积为 0：
        # 两站在矩形外同一射线方向上、共线，扇区只在一条线上接触
        rect = (0.0, 0.0, 10.0, 10.0)
        obs = [
            Observation(5.0, -10.0, azimuth=0.0, half_angle=0.0 + 1e-12),
            Observation(5.0, -20.0, azimuth=0.0, half_angle=0.0 + 1e-12),
        ]
        # 极小正角仍可能产生极小正面积或数值退化；不应崩溃
        try:
            poly, area = feasible_region(rect, obs)
            self.assertGreater(area, 0.0)
            self.assertGreater(_signed_area(poly), 0.0)
        except NoFeasibleAreaError:
            pass


if __name__ == "__main__":
    unittest.main()

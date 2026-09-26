"""几何算法与 API 测试。"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.geometry import (
    clip_polygon,
    feasible_region,
    rectangle_polygon,
    signed_area,
)
from app.main import app
from app.schemas import Observation, Point, SearchRect

TOL = 1e-9


def rect(x0=0.0, y0=0.0, x1=100.0, y1=100.0) -> SearchRect:
    return SearchRect(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


def obs(sx, sy, bearing, half_angle=10.0) -> Observation:
    return Observation(
        station=Point(x=sx, y=sy), bearing=bearing, half_angle=half_angle
    )


def point_in_poly(p, poly):
    """凸多边形包含判定（边界算在内），要求顶点逆时针排列。"""
    x, y = p
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross < -TOL:
            return False
    return True


# ---------------------------------------------------------------- 纯几何

def test_clip_halfplane():
    # 正方形保留 x >= 50 的一半
    poly = clip_polygon(rectangle_polygon(rect()), 1.0, 0.0, -50.0)
    assert len(poly) == 4
    assert signed_area(poly) == pytest.approx(5000.0, abs=1e-9)
    assert all(x >= 50.0 - TOL for x, _ in poly)


def test_single_45_degree_wedge_gives_triangle():
    # 原点指向正东（方位角 90°）、半角 45° 的扇区与单位正方形相交，
    # 得到三角形 (0,0),(1,0),(1,1)，面积 0.5。
    r = SearchRect(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
    poly, area = feasible_region(r, [obs(0.0, 0.0, 90.0, 45.0)])
    assert area == pytest.approx(0.5, abs=1e-9)
    assert len(poly) == 3  # 斜边上的近共线顶点应被简化删除
    assert point_in_poly((0.99, 0.5), poly)
    assert not point_in_poly((0.5, 0.99), poly)


def test_two_wedges_same_origin_intersect():
    # 原点两个宽扇区的交集为一个更窄的东北向扇区。
    r = SearchRect(x_min=-1.0, y_min=-1.0, x_max=1.0, y_max=1.0)
    poly, area = feasible_region(
        r, [obs(0.0, 0.0, 90.0, 45.0), obs(0.0, 0.0, 0.0, 45.0)]
    )
    # 交集为方位角 45°±0°... 两扇区各 45°，交集是方位角 [45°,45°]？
    # 东扇区：y<=x 且 y>=-x；北扇区：y>=x 且 y<=-x 的反向 → 公共部分 y=x 射线。
    # 因此面积应为 0（退化为直线），接口应判空。
    assert poly is None
    assert area == 0.0


def test_wide_wedges_cover_rectangle():
    # 南侧测站向北、北侧测站向南，45° 半角足以覆盖整个正方形，
    # 但左右仍被各自扇区裁掉一部分；这里用两个位置使结果为凸多边形。
    r = SearchRect(x_min=0.0, y_min=0.0, x_max=100.0, y_max=100.0)
    poly, area = feasible_region(
        r,
        [
            obs(50.0, -1000.0, 0.0, 45.0),   # 极远处向北，近似覆盖全宽
            obs(50.0, 1100.0, 180.0, 45.0),  # 极远处向南
        ],
    )
    # 距离 1000，半角 45°，横向容许 ±1000，整个矩形都在两扇区内。
    assert area == pytest.approx(10000.0, abs=1e-6)
    assert point_in_poly((50.0, 50.0), poly)
    assert point_in_poly((0.0, 0.0), poly)
    assert point_in_poly((100.0, 100.0), poly)


def test_station_inside_rectangle_wedge():
    # 测站位于矩形中心指向正西（方位角 270°），半角 10°。
    r = rect()
    poly, area = feasible_region(r, [obs(50.0, 50.0, 270.0, 10.0)])
    assert point_in_poly((10.0, 50.0), poly)
    assert not point_in_poly((90.0, 50.0), poly)
    assert not point_in_poly((10.0, 80.0), poly)
    # 中心线必然在区域内
    assert point_in_poly((0.0, 50.0), poly)


def test_contraction_is_consistent_with_each_observation():
    # 多扇区交集内的点必须落在每个扇区（在矩形边界以内抽样）。
    r = rect()
    observations = [
        obs(0.0, 0.0, 45.0, 15.0),
        obs(100.0, 0.0, 315.0, 20.0),
        obs(50.0, 120.0, 180.0, 25.0),
    ]
    poly, area = feasible_region(r, observations)
    assert area > 0.0
    # 结果多边形的所有顶点都必须满足每条观测的扇形不等式
    for vx, vy in poly:
        for o in observations:
            phi = math.degrees(math.atan2(vx - o.station.x, vy - o.station.y)) % 360.0
            delta = (phi - o.bearing + 180.0) % 360.0 - 180.0
            assert abs(delta) <= o.half_angle + 1e-8
    # 逆时针
    assert signed_area(poly) > 0.0


def test_empty_intersection_returns_none():
    # 两个互相矛盾的窄扇区：一个指向东，一个指向西，测站相同。
    r = rect()
    poly, area = feasible_region(
        r, [obs(50.0, 50.0, 90.0, 5.0), obs(50.0, 50.0, 270.0, 5.0)]
    )
    assert poly is None
    assert area == 0.0


def _in_wedge_by_bearing(x, y, o):
    """按方位角定义直接判断点是否在某条观测的扇区内（含边界）。"""
    dx = x - o.station.x
    dy = y - o.station.y
    if dx == 0.0 and dy == 0.0:
        return True
    bearing_to_point = math.degrees(math.atan2(dx, dy)) % 360.0
    delta = (bearing_to_point - o.bearing + 180.0) % 360.0 - 180.0
    return abs(delta) <= o.half_angle + 1e-9


def test_polygon_matches_bruteforce_definition():
    # 多组随机观测：网格上的每个点，裁剪多边形包含判定必须与
    # "逐扇区按方位角定义判定"完全一致。
    import random

    rng = random.Random(20260926)
    r = rect()
    for _ in range(30):
        observations = []
        for _ in range(rng.randint(2, 8)):
            observations.append(
                obs(
                    rng.uniform(-60.0, 160.0),
                    rng.uniform(-60.0, 160.0),
                    rng.uniform(0.0, 360.0),
                    rng.uniform(0.5, 45.0),
                )
            )
        poly, area = feasible_region(r, observations)

        grid = [i * 5.0 for i in range(21)]  # 0..100 共 21x21 个点
        for gx in grid:
            for gy in grid:
                by_def = all(_in_wedge_by_bearing(gx, gy, o) for o in observations)
                by_poly = point_in_poly((gx, gy), poly) if poly else False
                assert by_poly == by_def, (
                    f"mismatch at ({gx},{gy}): poly={by_poly} def={by_def}"
                )

        if poly is not None:
            assert area == pytest.approx(signed_area(poly), abs=1e-9)
            assert area > 0.0


# ---------------------------------------------------------------- API

client = TestClient(app)


def payload(observations, rectangle=None):
    rectangle = rectangle or {
        "x_min": 0.0,
        "y_min": 0.0,
        "x_max": 100.0,
        "y_max": 100.0,
    }
    return {"rectangle": rectangle, "observations": observations}


def test_api_success():
    body = payload([
        {"station": {"x": 0.0, "y": 0.0}, "bearing": 45.0, "half_angle": 20.0},
        {"station": {"x": 100.0, "y": 0.0}, "bearing": 315.0, "half_angle": 20.0},
    ])
    resp = client.post("/api/v1/feasible-region", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["area"] > 0.0
    assert len(data["vertices"]) >= 3


def test_api_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_api_empty_region_422():
    body = payload([
        {"station": {"x": 50.0, "y": 50.0}, "bearing": 90.0, "half_angle": 5.0},
        {"station": {"x": 50.0, "y": 50.0}, "bearing": 270.0, "half_angle": 5.0},
    ])
    resp = client.post("/api/v1/feasible-region", json=body)
    assert resp.status_code == 422


def test_api_invalid_half_angle_422():
    body = payload([
        {"station": {"x": 0.0, "y": 0.0}, "bearing": 45.0, "half_angle": 0.0},
        {"station": {"x": 100.0, "y": 0.0}, "bearing": 315.0, "half_angle": 20.0},
    ])
    resp = client.post("/api/v1/feasible-region", json=body)
    assert resp.status_code == 422


def test_api_wrong_observation_count_422():
    one = [
        {"station": {"x": 0.0, "y": 0.0}, "bearing": 45.0, "half_angle": 20.0}
    ]
    resp = client.post("/api/v1/feasible-region", json=payload(one))
    assert resp.status_code == 422

    nine = [
        {"station": {"x": 0.0, "y": float(i)}, "bearing": 45.0, "half_angle": 20.0}
        for i in range(9)
    ]
    resp = client.post("/api/v1/feasible-region", json=payload(nine))
    assert resp.status_code == 422


def test_api_degenerate_rectangle_422():
    body = payload(
        [
            {"station": {"x": 0.0, "y": 0.0}, "bearing": 45.0, "half_angle": 20.0},
            {"station": {"x": 1.0, "y": 1.0}, "bearing": 225.0, "half_angle": 20.0},
        ],
        rectangle={"x_min": 0.0, "y_min": 0.0, "x_max": 0.0, "y_max": 100.0},
    )
    resp = client.post("/api/v1/feasible-region", json=body)
    assert resp.status_code == 422

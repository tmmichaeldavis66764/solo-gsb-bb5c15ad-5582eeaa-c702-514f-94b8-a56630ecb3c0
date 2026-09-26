"""平面角扇区与矩形求交的几何核心（仅依赖标准库）。

坐标约定：
- 平面直角坐标 x(东向) / y(北向)。
- 方位角 azimuth 为从正北(y 轴正方向)顺时针旋转的角度(度)。
- 每条观测是以测站为顶点、中心指向方位角、半张开角 half_angle(0, 45] 度的角扇区。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class Observation:
    station_x: float
    station_y: float
    azimuth: float  # 度，从正北顺时针
    half_angle: float  # 度，(0, 45]


# ---------------------------------------------------------------------------
# 基础运算
# ---------------------------------------------------------------------------
def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _signed_area(poly: Sequence[Point]) -> float:
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - y1 * x2
    return area * 0.5


def _scale_from(values: Sequence[float]) -> float:
    m = max((abs(v) for v in values), default=0.0)
    return max(1.0, m)


def _wedge_constraints(obs: Observation) -> Tuple[Tuple[float, float, Point], Tuple[float, float, Point]]:
    """返回扇区两条边界射线对应的半平面约束 (a, b, S)。

    对点 P 令 v = P - S，约束为 a*vx + b*vy >= 0。
    方位角 alpha -> 标准角(从 x 轴正方向逆时针) theta = 90 - alpha。
    逆时针边界方向 d1 对应 theta1 = theta + beta，
    顺时针边界方向 d2 对应 theta2 = theta - beta，
    扇区内部满足 cross(d1, v) <= 0 且 cross(d2, v) >= 0。
    """
    theta = math.radians(90.0 - obs.azimuth)
    beta = math.radians(obs.half_angle)
    s = (obs.station_x, obs.station_y)

    t1 = theta + beta
    d1 = (math.cos(t1), math.sin(t1))
    # -cross(d1, v) = d1_y*vx - d1_x*vy >= 0
    c1 = (d1[1], -d1[0], s)

    t2 = theta - beta
    d2 = (math.cos(t2), math.sin(t2))
    # cross(d2, v) = d2_x*vy - d2_y*vx >= 0
    c2 = (-d2[1], d2[0], s)
    return c1, c2


def _eval_constraint(c: Tuple[float, float, Point], p: Point) -> float:
    a, b, s = c
    return a * (p[0] - s[0]) + b * (p[1] - s[1])


def _clip_by_halfplane(
    poly: Sequence[Point],
    constraint: Tuple[float, float, Point],
    tol: float,
) -> List[Point]:
    """Sutherland-Hodgman：保留 g(P) >= -tol 的一侧。"""
    if not poly:
        return []

    out: List[Point] = []
    s = poly[-1]
    gs = _eval_constraint(constraint, s)
    s_inside = gs >= -tol

    def intersection() -> Point:
        # 两端约束值差落入数值噪声带时（边与边界近乎重合），
        # 直接取边中点，避免小分母产生远处的假交点
        if abs(gs - ge) < 1e-12 * tol:
            return (0.5 * (s[0] + e[0]), 0.5 * (s[1] + e[1]))
        t = gs / (gs - ge)
        return (s[0] + t * (e[0] - s[0]), s[1] + t * (e[1] - s[1]))

    for e in poly:
        ge = _eval_constraint(constraint, e)
        e_inside = ge >= -tol

        if e_inside:
            if not s_inside:
                # s 在外、e 在内：求入边交点
                out.append(intersection())
            out.append(e)
        elif s_inside:
            # s 在内、e 在外：求出边交点
            out.append(intersection())

        s, gs, s_inside = e, ge, e_inside

    return out


def _clean_polygon(poly: Sequence[Point], scale: float) -> List[Point]:
    """去除重复点与共线中点。"""
    pt_tol = 1e-9 * scale
    area_tol = 1e-10 * scale * scale

    pts = list(poly)
    changed = True
    while changed and len(pts) >= 3:
        changed = False

        # 去除相邻重复点（含首尾）
        deduped: List[Point] = []
        for p in pts:
            if not deduped or math.hypot(p[0] - deduped[-1][0], p[1] - deduped[-1][1]) > pt_tol:
                deduped.append(p)
        while (
            len(deduped) >= 2
            and math.hypot(deduped[0][0] - deduped[-1][0], deduped[0][1] - deduped[-1][1]) <= pt_tol
        ):
            deduped.pop()
        if deduped != pts:
            pts = deduped
            changed = True

        # 去除严格位于相邻两点之间的共线点
        n = len(pts)
        if n >= 3:
            for i in range(n):
                a = pts[(i - 1) % n]
                b = pts[i]
                c = pts[(i + 1) % n]
                ab = _sub(b, a)
                bc = _sub(c, b)
                if (
                    abs(_cross(ab, bc)) <= area_tol
                    and ab[0] * bc[0] + ab[1] * bc[1] >= -area_tol
                ):
                    pts.pop(i)
                    changed = True
                    break

    return pts


class NoFeasibleAreaError(ValueError):
    """所有扇区与搜索矩形的交集不构成正面积区域。"""


def feasible_region(
    rect: Tuple[float, float, float, float],
    observations: Sequence[Observation],
) -> Tuple[List[Point], float]:
    """计算可行区域。

    rect = (xmin, ymin, xmax, ymax)，要求 xmax>xmin、ymax>ymin。
    返回 (逆时针顶点序列, 面积)。无正面积时抛出 NoFeasibleAreaError。
    """
    xmin, ymin, xmax, ymax = rect
    if not (xmax > xmin and ymax > ymin):
        raise ValueError("搜索矩形必须具有正的宽和高")
    if not (2 <= len(observations) <= 8):
        raise ValueError("观测数量必须在 2 到 8 条之间")

    # 初始矩形（逆时针）
    poly: List[Point] = [
        (xmin, ymin),
        (xmax, ymin),
        (xmax, ymax),
        (xmin, ymax),
    ]

    scale_values = [xmin, ymin, xmax, ymax]
    for o in observations:
        scale_values.extend((o.station_x, o.station_y))
    scale = _scale_from(scale_values)
    line_tol = 1e-10 * scale

    for obs in observations:
        for constraint in _wedge_constraints(obs):
            poly = _clip_by_halfplane(poly, constraint, line_tol)
            if len(poly) < 3:
                raise NoFeasibleAreaError("交集退化，无正面积可行区域")

    poly = _clean_polygon(poly, scale)
    if len(poly) < 3:
        raise NoFeasibleAreaError("交集退化，无正面积可行区域")

    area = _signed_area(poly)
    rect_area = (xmax - xmin) * (ymax - ymin)
    if abs(area) <= 1e-9 * rect_area:
        raise NoFeasibleAreaError("交集面积为零（或数值意义下退化）")

    if area < 0:  # 统一为逆时针
        poly.reverse()
        area = -area

    return poly, area

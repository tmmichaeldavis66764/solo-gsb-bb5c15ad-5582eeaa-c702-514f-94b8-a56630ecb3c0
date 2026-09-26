"""平面扇形与矩形逐次求交的几何算法。

每条测向观测表示为由测站出发的角扇区（楔形）：其中心线指向信号源
方位角 ``bearing``（自正北顺时针，单位：度），张开半角 ``half_angle``
（度，0 < half_angle <= 45）。

由于半角不超过 45°，每个扇形都是凸集，且等价于两条边界射线所界定的
半平面之交。可行区域即搜索矩形被全部扇形的半平面逐次裁剪后的凸多边形，
采用 Sutherland–Hodgman 算法实现。

坐标约定：平面直角坐标系 x 轴朝东、y 轴朝北；方位角自正北(y 轴正方向)
顺时针计量。
"""

from __future__ import annotations

import math

# 相对容差：用于消除浮点求交产生的近重复点、近共线点，以及判定面积为正。
_EPS = 1e-12


def _scale(rect) -> float:
    """返回问题的特征长度，用于构造数值容差。"""
    return max(
        rect.x_max - rect.x_min,
        rect.y_max - rect.y_min,
        abs(rect.x_min),
        abs(rect.x_max),
        abs(rect.y_min),
        abs(rect.y_max),
        1.0,
    )


def rectangle_polygon(rect):
    """以逆时针顺序返回搜索矩形的四个顶点。"""
    return [
        (rect.x_min, rect.y_min),
        (rect.x_max, rect.y_min),
        (rect.x_max, rect.y_max),
        (rect.x_min, rect.y_max),
    ]


def clip_polygon(poly, a, b, c):
    """用半平面 ``a*x + b*y + c >= 0`` 裁剪凸多边形（Sutherland–Hodgman）。"""
    if not poly:
        return []

    out: list[tuple[float, float]] = []
    s = poly[-1]
    ds = a * s[0] + b * s[1] + c
    for e in poly:
        de = a * e[0] + b * e[1] + c
        s_in = ds >= 0.0
        e_in = de >= 0.0

        if e_in:
            if not s_in:
                # s 在外、e 在内：加入入边交点
                t = ds / (ds - de)  # ds - de 不会为 0（异号或一边在界上）
                t = min(1.0, max(0.0, t))
                out.append((s[0] + (e[0] - s[0]) * t, s[1] + (e[1] - s[1]) * t))
            out.append(e)
        elif s_in:
            # s 在内、e 在外：加入出边交点
            t = ds / (ds - de)
            t = min(1.0, max(0.0, t))
            out.append((s[0] + (e[0] - s[0]) * t, s[1] + (e[1] - s[1]) * t))

        s, ds = e, de

    return out


def clip_sector(poly, obs):
    """用一条观测对应的角扇区裁剪多边形。

    方位角 ``b`` 的方向向量为 ``v(b) = (sin b, cos b)``（x 朝东、y 朝北）。
    设右/左边界方位角分别为 ``r = b - half_angle``、``l = b + half_angle``。
    以叉积（数学坐标下逆时针为正）表示，方向向量 ``d`` 落在扇区内当且仅当
    ``cross(v(r), d) <= 0`` 且 ``cross(v(l), d) >= 0``，展开为两个半平面：

      右边界:  `` cos r * (x - sx) - sin r * (y - sy) >= 0``
      左边界:  ``-cos l * (x - sx) + sin l * (y - sy) >= 0``
    """
    sr_x, sr_y = obs.station.x, obs.station.y
    r = math.radians(obs.bearing - obs.half_angle)
    l = math.radians(obs.bearing + obs.half_angle)
    cos_r, sin_r = math.cos(r), math.sin(r)
    cos_l, sin_l = math.cos(l), math.sin(l)

    poly = clip_polygon(
        poly, cos_r, -sin_r, -cos_r * sr_x + sin_r * sr_y
    )
    if not poly:
        return []

    poly = clip_polygon(
        poly, -cos_l, sin_l, cos_l * sr_x - sin_l * sr_y
    )
    return poly


def signed_area(poly) -> float:
    """鞋带公式求有向面积（逆时针为正）。"""
    n = len(poly)
    total = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total * 0.5


def _dedup(poly, tol):
    """去除首尾相接处及列表中重复的近重复顶点。"""
    if not poly:
        return []
    result = [poly[0]]
    for p in poly[1:]:
        q = result[-1]
        if abs(p[0] - q[0]) > tol or abs(p[1] - q[1]) > tol:
            result.append(p)
    if len(result) > 1:
        q = result[-1]
        f = result[0]
        if abs(f[0] - q[0]) <= tol and abs(f[1] - q[1]) <= tol:
            result.pop()
    return result


def simplify(poly, scale):
    """删除近共线的中间顶点，保留凸多边形的拐角顶点。

    ``scale`` 为问题特征长度，内部据此构造相对容差。
    """
    tol = _EPS * scale
    poly = _dedup(poly, tol)
    if len(poly) < 3:
        return poly

    collinear_tol = tol * tol
    changed = True
    while changed and len(poly) >= 3:
        changed = False
        n = len(poly)
        result: list[tuple[float, float]] = []
        for i in range(n):
            p = poly[(i - 1) % n]
            q = poly[i]
            r = poly[(i + 1) % n]
            cross = (q[0] - p[0]) * (r[1] - q[1]) - (q[1] - p[1]) * (r[0] - q[0])
            if abs(cross) > collinear_tol:
                result.append(q)
            else:
                # 删除近共线的 q，重启以重新判定相邻顶点。
                changed = True
                result.extend(poly[i + 1 :])
                poly = result
                break
    return poly


def feasible_region(rect, observations):
    """计算搜索矩形与全部观测扇形的交集。

    返回 ``(vertices, area)``，顶点按逆时针顺序；若交集不具有正面积，
    返回 ``(None, 0.0)``。
    """
    poly = rectangle_polygon(rect)
    for obs in observations:
        poly = clip_sector(poly, obs)
        if not poly:
            return None, 0.0

    scale = _scale(rect)
    tol = _EPS * scale
    poly = simplify(poly, scale)

    area_tol = _EPS * scale * scale
    area = signed_area(poly)
    if abs(area) <= area_tol:
        return None, 0.0

    # 数值保险：统一为逆时针方向。
    if area < 0.0:
        poly = list(reversed(poly))
        area = -area

    return poly, area

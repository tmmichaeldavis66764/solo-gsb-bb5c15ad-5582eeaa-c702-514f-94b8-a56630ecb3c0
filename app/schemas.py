"""请求/响应数据模型。"""

from __future__ import annotations

import math
from typing import List

from pydantic import BaseModel, Field, field_validator


class Point(BaseModel):
    """平面坐标点（x 朝东，y 朝北）。"""

    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("坐标必须为有限数值")
        return v


class SearchRect(BaseModel):
    """轴对齐搜索矩形，由两个对角点界定。"""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @field_validator("*")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("矩形边界必须为有限数值")
        return v


class Observation(BaseModel):
    """一条测站观测。

    - ``station``：测站坐标；
    - ``bearing``：指向信号源的方位角（度），自正北顺时针，范围 [0, 360)；
    - ``half_angle``：误差半角（度），0 < half_angle <= 45。
    """

    station: Point
    bearing: float = Field(ge=0.0, lt=360.0)
    half_angle: float = Field(gt=0.0, le=45.0)

    @field_validator("bearing", "half_angle")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("角度必须为有限数值")
        return v


class FeasibleRegionRequest(BaseModel):
    rectangle: SearchRect
    observations: List[Observation] = Field(min_length=2, max_length=8)

    @field_validator("observations")
    @classmethod
    def _not_empty(cls, v):
        # min_length 已校验，这里保留显式说明。
        if not v:
            raise ValueError("至少需要 2 条观测")
        return v


class Vertex(BaseModel):
    x: float
    y: float


class FeasibleRegionResponse(BaseModel):
    """可行区域：逆时针顶点序列与面积。"""

    vertices: List[Vertex]
    area: float

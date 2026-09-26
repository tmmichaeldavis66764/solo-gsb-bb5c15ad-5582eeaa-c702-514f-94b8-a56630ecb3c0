"""无线电测向可行区域 API。

POST /api/v1/feasible-region
    输入搜索矩形与 2~8 条测向观测，返回可行区域（各角扇区与矩形的交集）
    的逆时针顶点序列与面积；交集无正面积时返回 HTTP 422。
"""

from __future__ import annotations

from typing import List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .geometry import NoFeasibleAreaError, Observation, feasible_region

app = FastAPI(
    title="无线电测向可行区域 API",
    version="1.0.0",
    description=(
        "根据 2~8 个测站的角扇观测（每条为以测站为顶点的角扇区），"
        "在平面搜索矩形内计算可行信号源区域。"
    ),
)


class Rectangle(BaseModel):
    x_min: float = Field(..., description="搜索矩形西边界 x 坐标")
    y_min: float = Field(..., description="搜索矩形南边界 y 坐标")
    x_max: float = Field(..., description="搜索矩形东边界 x 坐标")
    y_max: float = Field(..., description="搜索矩形北边界 y 坐标")

    @model_validator(mode="after")
    def _validate(self) -> "Rectangle":
        if self.x_max <= self.x_min:
            raise ValueError("x_max 必须严格大于 x_min")
        if self.y_max <= self.y_min:
            raise ValueError("y_max 必须严格大于 y_min")
        return self


class BearingObservation(BaseModel):
    station_x: float = Field(..., description="测站 x 坐标")
    station_y: float = Field(..., description="测站 y 坐标")
    azimuth: float = Field(
        ...,
        description="指向信号源的方位角（度），从正北方向顺时针计；任意有限角度均可，将按 360 度归算",
    )
    half_angle: float = Field(
        ...,
        gt=0.0,
        le=45.0,
        description="测向误差半角（度），必须满足 0 < half_angle <= 45",
    )

    @model_validator(mode="after")
    def _validate_finite(self) -> "BearingObservation":
        for name, value in (
            ("station_x", self.station_x),
            ("station_y", self.station_y),
            ("azimuth", self.azimuth),
            ("half_angle", self.half_angle),
        ):
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{name} 必须为有限数值")
        return self


class FeasibleRegionRequest(BaseModel):
    rectangle: Rectangle
    observations: List[BearingObservation] = Field(
        ...,
        min_length=2,
        max_length=8,
        description="2~8 条测站观测",
    )


class Vertex(BaseModel):
    x: float
    y: float


class FeasibleRegionResponse(BaseModel):
    vertices: List[Vertex] = Field(
        ...,
        description="可行区域多边形顶点，按逆时针方向排列",
    )
    area: float = Field(..., gt=0.0, description="可行区域面积（坐标单位的平方）")
    vertex_count: int = Field(..., description="顶点数量")
    unit: Literal["square_coordinate_unit"] = "square_coordinate_unit"


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/v1/feasible-region",
    response_model=FeasibleRegionResponse,
    tags=["direction-finding"],
    summary="计算测向可行区域",
)
def compute_feasible_region(req: FeasibleRegionRequest) -> FeasibleRegionResponse:
    r = req.rectangle
    observations = [
        Observation(
            station_x=o.station_x,
            station_y=o.station_y,
            azimuth=o.azimuth,
            half_angle=o.half_angle,
        )
        for o in req.observations
    ]
    try:
        vertices, area = feasible_region(
            (r.x_min, r.y_min, r.x_max, r.y_max), observations
        )
    except NoFeasibleAreaError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_FEASIBLE_AREA",
                "message": str(exc),
            },
        )

    return FeasibleRegionResponse(
        vertices=[Vertex(x=x, y=y) for x, y in vertices],
        area=area,
        vertex_count=len(vertices),
    )

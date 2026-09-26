"""无线电测向可行区域 API。

POST /api/v1/feasible-region
    输入搜索矩形与 2~8 条测站观测，返回各角扇区与矩形逐次求交所得
    凸多边形的逆时针顶点及面积；交集没有正面积时返回 HTTP 422。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .geometry import feasible_region
from .schemas import (
    FeasibleRegionRequest,
    FeasibleRegionResponse,
    Vertex,
)

app = FastAPI(
    title="无线电测向可行区域 API",
    description=(
        "将每条测向观测表示为由测站出发的角扇区，与搜索矩形逐次求交，"
        "返回交集的逆时针顶点和面积。"
    ),
    version="1.0.0",
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.post(
    "/api/v1/feasible-region",
    response_model=FeasibleRegionResponse,
    tags=["direction-finding"],
    responses={
        422: {"description": "请求参数非法，或可行区域不具有正面积"},
    },
)
def compute_feasible_region(req: FeasibleRegionRequest):
    rect = req.rectangle
    if rect.x_max <= rect.x_min or rect.y_max <= rect.y_min:
        raise HTTPException(
            status_code=422,
            detail="矩形必须满足 x_max > x_min 且 y_max > y_min",
        )

    vertices, area = feasible_region(rect, req.observations)
    if vertices is None:
        # 与正常的请求体校验失败使用相同状态码 422。
        return JSONResponse(
            status_code=422,
            content={"detail": "全部观测扇形与搜索矩形的交集不具有正面积"},
        )

    return FeasibleRegionResponse(
        vertices=[Vertex(x=x, y=y) for x, y in vertices],
        area=area,
    )

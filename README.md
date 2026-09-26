# 无线电测向可行区域 API

基于 **Python 3.12 + FastAPI** 的服务：给定平面坐标系中的一个轴对齐搜索矩形，以及
2～8 个测站的测向观测（每条观测是以测站为顶点、以指向信号源的方位角为中心、
带误差半角的**角扇区**），计算所有角扇区与搜索矩形逐次求交后的**可行区域多边形**，
返回其**逆时针顶点序列与面积**。交集不构成正面积区域时返回 **HTTP 422**。

## 一条命令启动

前置条件：已安装 Docker（含 Compose 插件，即 `docker compose` 子命令）。

```bash
docker compose up --build -d
```

启动后服务监听在：

- API 地址：`http://localhost:8000`
- 交互文档（Swagger UI）：`http://localhost:8000/docs`
- OpenAPI Schema：`http://localhost:8000/openapi.json`
- 健康检查：`http://localhost:8000/health`

停止并移除：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

## 必要配置

默认无需任何配置即可运行。可选配置（通过环境变量或项目根目录 `.env` 文件）：

| 变量        | 默认值 | 说明                                   |
| ----------- | ------ | -------------------------------------- |
| `HOST_PORT` | `8000` | 宿主机映射端口（如本机 8000 被占用可改）|
| `PORT`      | `8000` | 容器内监听端口（同时映射到宿主机同端口）|

例如改用宿主机 18000 端口：

```bash
HOST_PORT=18000 docker compose up --build -d
# 访问 http://localhost:18000/docs
```

## 坐标与角度约定

- 平面直角坐标：`x` 轴朝东、`y` 轴朝北，单位自定（面积单位为坐标单位的平方）。
- 搜索矩形：轴对齐矩形，由 `x_min / y_min / x_max / y_max` 定义，要求严格正宽高。
- 方位角 `azimuth`：从**正北**（y 轴正方向）**顺时针**计的角度（度）；可取任意有限
  数值，超出 `[0, 360)` 会按周期等价处理（如 `-90`、`450`）。
- 误差半角 `half_angle`：满足 **`0 < half_angle <= 45`**（度）。扇区为从中心方位
  分别向逆时针、顺时针各张开 `half_angle` 的无界角域。

## API

### `POST /api/v1/feasible-region`

请求体：

```json
{
  "rectangle": {
    "x_min": 0.0,
    "y_min": 0.0,
    "x_max": 100.0,
    "y_max": 100.0
  },
  "observations": [
    {"station_x": 0.0,  "station_y": 0.0,  "azimuth": 45.0,  "half_angle": 10.0},
    {"station_x": 100.0,"station_y": 0.0,  "azimuth": 315.0, "half_angle": 10.0}
  ]
}
```

成功响应 `200`（顶点按**逆时针**排列）：

```json
{
  "vertices": [
    {"x": 23.4, "y": 23.4},
    {"x": 50.0, "y": 76.6},
    {"x": 76.6, "y": 23.4}
  ],
  "area": 1414.2,
  "vertex_count": 3,
  "unit": "square_coordinate_unit"
}
```

交集无正面积时返回 `422`：

```json
{
  "detail": {
    "code": "NO_FEASIBLE_AREA",
    "message": "交集退化，无正面积可行区域"
  }
}
```

请求参数不合法（观测数不在 2～8、半角超出 `(0, 45]`、矩形宽高非正等）同样返回 `422`
（FastAPI 标准校验错误体）。

调用示例：

```bash
curl -s -X POST http://localhost:8000/api/v1/feasible-region \
  -H 'Content-Type: application/json' \
  -d '{
    "rectangle": {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100},
    "observations": [
      {"station_x": 0, "station_y": 0, "azimuth": 45, "half_angle": 10},
      {"station_x": 100, "station_y": 0, "azimuth": 315, "half_angle": 10}
    ]
  }'
```

## 实现说明

- 每个角扇区表示为两条以测站为原点的边界射线，各定义一个线性半平面；搜索矩形是
  初始凸多边形（逆时针）。
- 依次用 Sutherland–Hodgman 凸多边形裁剪算法，以每条扇区边界的半平面裁剪当前
  多边形（2～8 条观测共 4～16 次裁剪）。
- 裁剪结果去除重复点与共线中点后，用鞋带公式计算有符号面积；面积非正（数值容差内
  退化）判定为无正面积，返回 422；否则统一翻转为逆时针顺序返回。

## 本地开发 / 测试

不使用 Docker 时（需要 Python 3.11+，几何核心仅用标准库）：

```bash
# 仅几何核心测试，无需任何第三方依赖
python3 -m unittest discover -s tests -v

# 安装依赖后运行完整服务与 API 测试
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python3 -m unittest discover -s tests -v
```

镜像构建时会自动执行全部单元测试（几何 + API），测试失败将中断构建。

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── geometry.py      # 角扇区 / 半平面裁剪几何核心（纯标准库）
│   └── main.py          # FastAPI 路由与请求模型
├── tests/
│   ├── test_geometry.py # 几何核心单元测试
│   └── test_api.py      # API 端到端测试
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

# 无线电测向可行区域 API（Python + FastAPI）

给定平面直角坐标系中的一个**搜索矩形**与 **2～8 条测站观测**，把每条观测
表示为由测站出发的**角扇区（楔形）**，将所有扇区与搜索矩形**逐次求交**，
返回交集凸多边形的**逆时针顶点序列**及其**面积**；当交集不具有正面积时
返回 **HTTP 422**。

- 坐标系：x 轴朝东、y 轴朝北（平面直角坐标系）。
- 方位角 `bearing`：自**正北（+y 方向）顺时针**计量，单位为度，范围 `[0, 360)`。
- 误差半角 `half_angle`：单位为度，满足 `0 < half_angle <= 45`。
- 因为半角不超过 45°，每个扇区都是凸集，且等价于其两条边界射线界定的两个
  半平面的交集；服务端用 Sutherland–Hodgman 算法对矩形逐次裁剪。

## 一条命令启动

需要本机已安装 Docker 与 Docker Compose 插件，然后在项目根目录执行：

```bash
docker compose up --build
```

服务启动后监听：

- 健康检查：<http://localhost:8000/health>
- Swagger 交互文档：<http://localhost:8000/docs>
- ReDoc 文档：<http://localhost:8000/redoc>
- 接口地址（POST）：`http://localhost:8000/api/v1/feasible-region`

## 必要配置

唯一可配置项是**宿主机映射端口**，默认 `8000`。如 8000 端口被占用，可通过
环境变量覆盖：

```bash
HOST_PORT=9000 docker compose up --build
```

此时接口地址变为 `http://localhost:9000/api/v1/feasible-region`
（容器内始终监听 8000）。无需数据库或其他外部依赖。

## 请求示例

```bash
curl -X POST http://localhost:8000/api/v1/feasible-region \
  -H "Content-Type: application/json" \
  -d '{
    "rectangle": {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100},
    "observations": [
      {"station": {"x": 0, "y": 0},   "bearing": 45.0,  "half_angle": 20.0},
      {"station": {"x": 100, "y": 0}, "bearing": 315.0, "half_angle": 20.0}
    ]
  }'
```

请求体字段：

| 字段 | 说明 |
| --- | --- |
| `rectangle.x_min/y_min/x_max/y_max` | 轴对齐搜索矩形边界，要求 `x_max > x_min`、`y_max > y_min` |
| `observations` | 观测列表，数量 **2～8** 条 |
| `observations[].station.x/y` | 测站坐标（可在矩形内或矩形外） |
| `observations[].bearing` | 自正北顺时针的方位角（度），`[0, 360)` |
| `observations[].half_angle` | 误差半角（度），`(0, 45]` |

成功响应（`200`）：

```json
{
  "vertices": [
    {"x": 50.0, "y": 14.34},
    {"x": 85.66, "y": 50.0},
    {"x": 50.0, "y": 50.0}
  ],
  "area": 1269.5
}
```

- `vertices` 按**逆时针**顺序给出，已合并近重复点、删除近共线点；
- `area` 为鞋带公式求得的正面积。

以下情况返回 **422 Unprocessable Entity**：

- 请求体校验失败（观测数量不在 2～8、半角越界、矩形退化、坐标非有限数等）；
- 所有扇区与矩形的交集为空或退化为点/线段，**不具有正面积**。

## 本地开发（不使用 Docker）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload          # 启动开发服务器
pytest                                 # 运行测试
```

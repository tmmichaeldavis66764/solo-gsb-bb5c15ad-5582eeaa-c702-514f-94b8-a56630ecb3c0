"""API 层测试：需要 fastapi + httpx（Docker 构建时运行；本地缺依赖时自动跳过）。"""

import unittest

try:
    from fastapi.testclient import TestClient
    from app.main import app

    _HAS_DEPS = True
except ImportError:  # pragma: no cover - 本地无第三方依赖时
    _HAS_DEPS = False


@unittest.skipUnless(_HAS_DEPS, "fastapi/httpx 未安装，跳过 API 测试")
class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_basic_region(self):
        r = self.client.post(
            "/api/v1/feasible-region",
            json={
                "rectangle": {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100},
                "observations": [
                    {"station_x": 0, "station_y": 0, "azimuth": 45, "half_angle": 10},
                    {"station_x": 100, "station_y": 0, "azimuth": 315, "half_angle": 10},
                ],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertGreater(data["area"], 0)
        self.assertEqual(data["vertex_count"], len(data["vertices"]))
        self.assertGreaterEqual(data["vertex_count"], 3)

    def test_no_feasible_area_returns_422(self):
        r = self.client.post(
            "/api/v1/feasible-region",
            json={
                "rectangle": {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100},
                "observations": [
                    {"station_x": 10, "station_y": 10, "azimuth": 135, "half_angle": 5},
                    {"station_x": 90, "station_y": 90, "azimuth": 315, "half_angle": 5},
                ],
            },
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "NO_FEASIBLE_AREA")

    def test_validation_error_half_angle(self):
        r = self.client.post(
            "/api/v1/feasible-region",
            json={
                "rectangle": {"x_min": 0, "y_min": 0, "x_max": 1, "y_max": 1},
                "observations": [
                    {"station_x": 0, "station_y": 0, "azimuth": 0, "half_angle": 0},
                    {"station_x": 1, "station_y": 1, "azimuth": 0, "half_angle": 90},
                ],
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_validation_error_observation_count(self):
        r = self.client.post(
            "/api/v1/feasible-region",
            json={
                "rectangle": {"x_min": 0, "y_min": 0, "x_max": 1, "y_max": 1},
                "observations": [
                    {"station_x": 0, "station_y": 0, "azimuth": 0, "half_angle": 5}
                ],
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_openapi_available(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()

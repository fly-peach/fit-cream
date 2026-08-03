"""健康检查与应用基础端点"""

from app.config import settings


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_openapi_available(client):
    resp = await client.get("/openapi.json")
    if settings.API_DOCS_ENABLED:
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        # 关键路由均已注册
        assert "/api/auth/login" in paths
        assert "/api/plans" in paths
        assert "/api/checkins" in paths
    else:
        # 默认关闭 API 文档，openapi.json 应返回 404
        assert resp.status_code == 404


async def test_unknown_api_path_returns_json_404(client):
    resp = await client.get("/api/definitely-not-exists")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}

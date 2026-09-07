import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_problem_details_on_validation_error_422() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 传递缺少必填字段的 POST 请求
        response = await client.post(
            "/v1/materials",
            json={"name": "incomplete"},
            headers={"X-Request-ID": "req-test-422"},
        )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 422
    assert body["title"] == "请求校验失败"
    assert body["request_id"] == "req-test-422"
    assert "errors" in body


@pytest.mark.asyncio
async def test_problem_details_on_not_found_404() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/nonexistent-endpoint-for-404",
            headers={"X-Request-ID": "req-test-404"},
        )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["request_id"] == "req-test-404"


@pytest.mark.asyncio
async def test_problem_details_on_unauthorized_401() -> None:
    transport = httpx.ASGITransport(app=app)
    # 测试未传 token 访问审核端点
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/workflow/observations/01a06670-0000-7000-8000-000000000009/review",
            json={"decision": "HUMAN_REVIEWED", "reviewer": "Tester"},
            headers={"X-Request-ID": "req-test-401", "If-Match": 'W/"1"'},
        )
    # 当 PCM_REVIEWER_TOKEN 未配置时返回 503，配置但未提供或错误时返回 401
    assert response.status_code in {401, 503}
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["request_id"] == "req-test-401"
    assert body["status"] in {401, 503}


@pytest.mark.asyncio
async def test_problem_details_request_id_generated_when_omitted() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 客户端未传 X-Request-ID 时发起请求
        response = await client.post(
            "/v1/materials",
            json={"name": "incomplete"},
        )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    header_req_id = response.headers.get("X-Request-ID")
    assert header_req_id is not None and len(header_req_id) > 0
    body = response.json()
    assert body["request_id"] is not None and len(body["request_id"]) > 0
    # 验证响应体 request_id 与响应头一致
    assert body["request_id"] == header_req_id

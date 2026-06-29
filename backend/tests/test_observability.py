"""Testes de observabilidade e métricas."""

from app.observability.metrics import (
    HTTP_REQUESTS,
    render_prometheus,
    path_group,
    record_http_request,
    record_scheduler_job,
)


def test_path_group_normalization():
    assert path_group("/health/live") == "/health"
    assert path_group("/metrics") == "/metrics"
    assert path_group("/api/v1/indicators/executive") == "/api/v1/indicators"
    assert path_group("/api/v1/reports/generate") == "/api/v1/reports"


def test_prometheus_render_includes_counters():
    record_http_request("GET", "/health/live", 200, 0.01)
    record_scheduler_job("test_job", True)
    body = render_prometheus()
    assert "sinidu_http_requests_total" in body
    assert "sinidu_scheduler_runs_total" in body
    assert 'status="200"' in body


def test_http_requests_increment():
    before = sum(HTTP_REQUESTS.snapshot().values())
    record_http_request("POST", "/api/v1/onboarding/ensure/2611606", 200, 0.05)
    after = sum(HTTP_REQUESTS.snapshot().values())
    assert after >= before + 1

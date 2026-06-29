from __future__ import annotations

import threading
import time
from typing import Any


class _Counter:
    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def snapshot(self) -> dict[tuple[tuple[str, str], ...], float]:
        with self._lock:
            return dict(self._values)


class _Gauge:
    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value

    def snapshot(self) -> dict[tuple[tuple[str, str], ...], float]:
        with self._lock:
            return dict(self._values)


class _Histogram:
    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self._sum: dict[tuple[tuple[str, str], ...], float] = {}
        self._count: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._sum[key] = self._sum.get(key, 0.0) + value
            self._count[key] = self._count.get(key, 0.0) + 1.0

    def snapshot(self) -> tuple[dict[tuple[tuple[str, str], ...], float], dict[tuple[tuple[str, str], ...], float]]:
        with self._lock:
            return dict(self._sum), dict(self._count)


HTTP_REQUESTS = _Counter(
    "sinidu_http_requests_total",
    "Total de requisições HTTP",
    ("method", "path_group", "status"),
)
HTTP_DURATION = _Histogram(
    "sinidu_http_request_duration_seconds",
    "Duração das requisições HTTP em segundos",
    ("method", "path_group"),
)
SCHEDULER_RUNS = _Counter(
    "sinidu_scheduler_runs_total",
    "Execuções de jobs agendados",
    ("job", "status"),
)
INTEGRATION_SYNC = _Counter(
    "sinidu_integration_sync_total",
    "Sincronizações de integração por fonte",
    ("source", "status"),
)
BACKUP_RUNS = _Counter(
    "sinidu_postgis_backup_total",
    "Backups PostGIS",
    ("status"),
)

APP_START_TIME = time.time()


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + inner + "}"


def _emit_counter(lines: list[str], counter: _Counter) -> None:
    lines.append(f"# HELP {counter.name} {counter.help}")
    lines.append(f"# TYPE {counter.name} counter")
    for labels, value in counter.snapshot().items():
        lines.append(f"{counter.name}{_format_labels(labels)} {value}")


def _emit_gauge(lines: list[str], gauge: _Gauge) -> None:
    lines.append(f"# HELP {gauge.name} {gauge.help}")
    lines.append(f"# TYPE {gauge.name} gauge")
    for labels, value in gauge.snapshot().items():
        lines.append(f"{gauge.name}{_format_labels(labels)} {value}")


def _emit_histogram(lines: list[str], hist: _Histogram) -> None:
    sums, counts = hist.snapshot()
    lines.append(f"# HELP {hist.name} {hist.help}")
    lines.append(f"# TYPE {hist.name} histogram")
    for labels, total in sums.items():
        label_str = _format_labels(labels)
        count = counts.get(labels, 0.0)
        lines.append(f"{hist.name}_sum{label_str} {total}")
        lines.append(f"{hist.name}_count{label_str} {count}")


UPTIME_GAUGE = _Gauge("sinidu_process_uptime_seconds", "Tempo desde o boot da API")


def path_group(path: str) -> str:
    if path.startswith("/health"):
        return "/health"
    if path.startswith("/metrics"):
        return "/metrics"
    if path.startswith("/api/v1/indicators"):
        return "/api/v1/indicators"
    if path.startswith("/api/v1/reports"):
        return "/api/v1/reports"
    if path.startswith("/api/v1/onboarding"):
        return "/api/v1/onboarding"
    if path.startswith("/api/v1/integrations"):
        return "/api/v1/integrations"
    if path.startswith("/api/v1/monitoring"):
        return "/api/v1/monitoring"
    if path.startswith("/api/v1"):
        return "/api/v1"
    if path == "/":
        return "/"
    return "/other"


def render_prometheus() -> str:
    UPTIME_GAUGE.set(time.time() - APP_START_TIME)
    lines: list[str] = []
    _emit_counter(lines, HTTP_REQUESTS)
    _emit_histogram(lines, HTTP_DURATION)
    _emit_counter(lines, SCHEDULER_RUNS)
    _emit_counter(lines, INTEGRATION_SYNC)
    _emit_counter(lines, BACKUP_RUNS)
    _emit_gauge(lines, UPTIME_GAUGE)
    return "\n".join(lines) + "\n"


def record_http_request(method: str, path: str, status_code: int, duration_s: float) -> None:
    group = path_group(path)
    HTTP_REQUESTS.inc(method=method, path_group=group, status=str(status_code))
    HTTP_DURATION.observe(duration_s, method=method, path_group=group)


def record_scheduler_job(job: str, ok: bool) -> None:
    SCHEDULER_RUNS.inc(job=job, status="ok" if ok else "error")


def record_integration_sync(source: str, ok: bool, count: int = 1) -> None:
    INTEGRATION_SYNC.inc(amount=count, source=source, status="ok" if ok else "error")


def record_backup(ok: bool) -> None:
    BACKUP_RUNS.inc(status="ok" if ok else "error")

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DASHBOARD_CONFIG = REPO_ROOT / "config" / "dashboard.yaml"
SLO_CONFIG = REPO_ROOT / "config" / "slo.yaml"
WINDOW_MINUTES = 60


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered) / 100) - 1)
    return round(ordered[min(index, len(ordered) - 1)], 2)


def _records_in_window(now: datetime, start: datetime) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is not None and start <= timestamp <= now:
            records.append(record)
    return records


def _panel_config(dashboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    panels = dashboard.get("panels", [])
    if not isinstance(panels, list):
        return {}
    return {
        panel["id"]: panel
        for panel in panels
        if isinstance(panel, dict) and isinstance(panel.get("id"), str)
    }


def _threshold_text(panel: dict[str, Any]) -> str:
    threshold = panel.get("threshold", {})
    operators = {"lte": "≤", "gte": "≥"}
    operator = operators.get(threshold.get("operator"), "")
    value = threshold.get("value", "—")
    unit = panel.get("unit", "")
    if isinstance(value, (int, float)):
        if unit == "usd":
            formatted = f"${value:,.2f}"
        elif unit == "ms":
            formatted = f"{value:,.0f} ms"
        elif unit == "percent":
            formatted = f"{value:g}%"
        elif unit == "score_0_to_1":
            formatted = f"{value:.2f}"
        elif unit == "requests_per_minute":
            formatted = f"{value:g} req/min"
        elif unit == "tokens":
            formatted = f"{value:,.0f} tokens"
        else:
            formatted = str(value)
    else:
        formatted = str(value)
    return f"Target {operator} {formatted}".strip()


def build_dashboard_data(now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = current - timedelta(minutes=WINDOW_MINUTES)
    records = _records_in_window(current, start)
    panels = _panel_config(_load_yaml(DASHBOARD_CONFIG).get("dashboard", {}))
    slo = _load_yaml(SLO_CONFIG).get("primary_slo", {})

    by_event: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        event = record.get("event")
        if isinstance(event, str):
            by_event.setdefault(event, []).append(record)

    requests = by_event.get("request_received", [])
    failures = by_event.get("request_failed", [])
    responses = by_event.get("response_sent", [])
    latencies = [float(row["latency_ms"]) for row in responses if isinstance(row.get("latency_ms"), (int, float))]
    ttft = [float(row["ttft_ms"]) for row in responses if isinstance(row.get("ttft_ms"), (int, float))]
    costs = [float(row["cost_usd"]) for row in responses if isinstance(row.get("cost_usd"), (int, float))]
    tokens_in = [int(row["tokens_in"]) for row in responses if isinstance(row.get("tokens_in"), (int, float))]
    tokens_out = [int(row["tokens_out"]) for row in responses if isinstance(row.get("tokens_out"), (int, float))]
    quality = [float(row["quality_score"]) for row in responses if isinstance(row.get("quality_score"), (int, float))]
    tool_results = [row.get("tool_success") for row in records if isinstance(row.get("tool_success"), bool)]

    minute_start = current.replace(second=0, microsecond=0) - timedelta(minutes=WINDOW_MINUTES - 1)
    labels = [(minute_start + timedelta(minutes=index)).strftime("%H:%M") for index in range(WINDOW_MINUTES)]
    counts_by_minute = [0] * WINDOW_MINUTES
    failures_by_minute = [0] * WINDOW_MINUTES
    cost_by_minute = [0.0] * WINDOW_MINUTES

    def bucket_index(record: dict[str, Any]) -> int | None:
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is None:
            return None
        index = int((timestamp - minute_start).total_seconds() // 60)
        return index if 0 <= index < WINDOW_MINUTES else None

    for record in requests:
        index = bucket_index(record)
        if index is not None:
            counts_by_minute[index] += 1
    for record in failures:
        index = bucket_index(record)
        if index is not None:
            failures_by_minute[index] += 1
    for record in responses:
        index = bucket_index(record)
        value = record.get("cost_usd")
        if index is not None and isinstance(value, (int, float)):
            cost_by_minute[index] += float(value)

    error_rate = (len(failures) / len(requests) * 100) if requests else None
    retrieval_success = (
        sum(tool_result is True for tool_result in tool_results) / len(tool_results) * 100
        if tool_results
        else None
    )
    target_latency = float(panels.get("latency", {}).get("threshold", {}).get("value", 3000))
    slo_target = float(slo.get("target_percent", 99.5))
    good_responses = sum(value <= target_latency for value in latencies)
    slo_good_rate = good_responses / len(requests) * 100 if requests else None

    def panel(
        panel_id: str,
        *,
        main_label: str,
        main_value: float | int | None,
        stats: list[dict[str, Any]],
        chart_kind: str,
        chart_values: list[float | int],
        chart_labels: list[str] | None = None,
        chart_threshold: float | None = None,
    ) -> dict[str, Any]:
        config = panels.get(panel_id, {})
        return {
            "id": panel_id,
            "title": config.get("title", panel_id.title()),
            "unit": config.get("unit", ""),
            "main_label": main_label,
            "main_value": main_value,
            "stats": stats,
            "threshold_text": _threshold_text(config),
            "chart": {
                "kind": chart_kind,
                "values": chart_values,
                "labels": chart_labels or [],
                "threshold": chart_threshold,
            },
        }

    response_rows_sorted = sorted(
        responses,
        key=lambda row: _parse_timestamp(row.get("ts")) or start,
    )
    latency_series = [
        float(row["latency_ms"])
        for row in response_rows_sorted[-30:]
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    quality_series = [
        float(row["quality_score"])
        for row in response_rows_sorted[-30:]
        if isinstance(row.get("quality_score"), (int, float))
    ]
    minute_error_rates = [
        (failures_by_minute[index] / counts_by_minute[index] * 100)
        if counts_by_minute[index]
        else 0.0
        for index in range(WINDOW_MINUTES)
    ]

    dashboard_panels = [
        panel(
            "latency",
            main_label="P95 latency",
            main_value=_percentile(latencies, 95),
            stats=[
                {"label": "P50", "value": _percentile(latencies, 50), "unit": "ms"},
                {"label": "P95", "value": _percentile(latencies, 95), "unit": "ms"},
                {"label": "P99", "value": _percentile(latencies, 99), "unit": "ms"},
                {"label": "TTFT P95", "value": _percentile(ttft, 95), "unit": "ms"},
            ],
            chart_kind="line",
            chart_values=latency_series,
            chart_labels=[str(index + 1) for index in range(len(latency_series))],
            chart_threshold=target_latency,
        ),
        panel(
            "traffic",
            main_label="Requests / min",
            main_value=round(len(requests) / WINDOW_MINUTES, 2),
            stats=[{"label": "Requests in window", "value": len(requests), "unit": "count"}],
            chart_kind="bars",
            chart_values=counts_by_minute,
            chart_labels=labels,
            chart_threshold=float(panels.get("traffic", {}).get("threshold", {}).get("value", 1)),
        ),
        panel(
            "errors",
            main_label="Error rate",
            main_value=round(error_rate, 2) if error_rate is not None else None,
            stats=[
                {"label": "Failed requests", "value": len(failures), "unit": "count"},
                {"label": "Retrieval success", "value": round(retrieval_success, 2) if retrieval_success is not None else None, "unit": "percent"},
            ],
            chart_kind="bars",
            chart_values=minute_error_rates,
            chart_labels=labels,
            chart_threshold=float(panels.get("errors", {}).get("threshold", {}).get("value", 2)),
        ),
        panel(
            "cost",
            main_label="Total cost",
            main_value=round(sum(costs), 6),
            stats=[{"label": "Mean / response", "value": round(sum(costs) / len(costs), 6) if costs else None, "unit": "usd"}],
            chart_kind="bars",
            chart_values=cost_by_minute,
            chart_labels=labels,
        ),
        panel(
            "tokens",
            main_label="Total tokens",
            main_value=sum(tokens_in) + sum(tokens_out),
            stats=[
                {"label": "Input", "value": sum(tokens_in), "unit": "tokens"},
                {"label": "Output", "value": sum(tokens_out), "unit": "tokens"},
            ],
            chart_kind="bars",
            chart_values=[sum(tokens_in), sum(tokens_out)],
            chart_labels=["Input", "Output"],
        ),
        panel(
            "quality",
            main_label="Mean quality",
            main_value=round(sum(quality) / len(quality), 3) if quality else None,
            stats=[{"label": "Responses scored", "value": len(quality), "unit": "count"}],
            chart_kind="line",
            chart_values=quality_series,
            chart_labels=[str(index + 1) for index in range(len(quality_series))],
            chart_threshold=float(panels.get("quality", {}).get("threshold", {}).get("value", 0.75)),
        ),
    ]

    if not requests:
        slo_status = "NO DATA"
    elif slo_good_rate is not None and slo_good_rate >= slo_target:
        slo_status = "MEETING TARGET"
    else:
        slo_status = "NEEDS REVIEW"

    return {
        "title": _load_yaml(DASHBOARD_CONFIG).get("dashboard", {}).get("title", "Monitoring dashboard"),
        "generated_at": current.isoformat(timespec="seconds"),
        "window_minutes": WINDOW_MINUTES,
        "refresh_seconds": 30,
        "record_count": len(records),
        "slo": {
            "name": slo.get("name", "primary_slo"),
            "target_percent": slo_target,
            "good_rate_percent": round(slo_good_rate, 2) if slo_good_rate is not None else None,
            "status": slo_status,
        },
        "panels": dashboard_panels,
    }


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>Monitoring dashboard</title>
  <style>
    :root { color-scheme: dark; --bg:#0b1020; --card:#151d31; --line:#26344e; --text:#edf2ff; --muted:#a1aec7; --accent:#8b9cff; --good:#38d996; --warn:#ffb454; --bad:#ff7272; }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 50% -30%,#202d4c 0,var(--bg) 48%); color:var(--text); font:15px/1.45 Segoe UI,Arial,sans-serif; }
    main { max-width:1440px; margin:0 auto; padding:32px 28px 40px; }
    .top { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; margin-bottom:24px; }
    h1 { font-size:27px; margin:0 0 6px; letter-spacing:-.03em; }
    .sub,.updated { color:var(--muted); font-size:13px; }
    .slo { min-width:260px; padding:15px 18px; border:1px solid var(--line); border-radius:14px; background:#111a2c; }
    .slo-label { color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; }
    .slo-main { display:flex; justify-content:space-between; gap:10px; align-items:baseline; margin-top:5px; font-size:21px; font-weight:700; }
    .status { font-size:10px; letter-spacing:.08em; color:var(--good); }
    .status.bad { color:var(--bad); } .status.empty { color:var(--warn); }
    .grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
    .card { min-width:0; min-height:265px; padding:19px 20px 16px; border:1px solid var(--line); border-radius:16px; background:linear-gradient(155deg,#182239,var(--card) 68%); box-shadow:0 12px 30px #05091455; }
    .card-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
    h2 { margin:0; font-size:15px; font-weight:650; }
    .tag { border:1px solid #344665; border-radius:99px; padding:3px 8px; color:var(--muted); font-size:10px; white-space:nowrap; }
    .main-metric { margin-top:16px; font-size:30px; font-weight:700; letter-spacing:-.04em; }
    .main-label { color:var(--muted); font-size:12px; margin-top:1px; }
    .stats { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:14px; }
    .stat { display:flex; gap:5px; color:var(--muted); font-size:11px; }
    .stat strong { color:var(--text); font-weight:600; }
    .chart { height:74px; margin-top:10px; overflow:hidden; }
    .chart svg { width:100%; height:100%; display:block; overflow:visible; }
    .threshold { color:#c6d0e7; font-size:11px; margin-top:6px; }
    .threshold b { color:var(--warn); font-weight:600; }
    .foot { display:flex; justify-content:space-between; margin-top:20px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; }
    .empty-note { color:var(--muted); padding-top:26px; text-align:center; }
    @media(max-width:1000px) { .grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media(max-width:640px) { main { padding:22px 14px; } .top { display:block; } .slo { margin-top:18px; } .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <header class="top">
    <div>
      <h1 id="title">K4-L3B Day 13 Monitoring &amp; LLMOps</h1>
      <div class="sub">Operational view · last <span id="window">60</span> minutes · source: data/logs.jsonl</div>
      <div class="updated" id="updated">Loading local logs…</div>
    </div>
    <section class="slo" aria-label="Primary SLO">
      <div class="slo-label">Primary SLO · 28 day window</div>
      <div class="slo-main"><span><span id="slo-rate">—</span><small>%</small></span><span class="status empty" id="slo-status">NO DATA</span></div>
      <div class="sub">Target <span id="slo-target">99.5</span>% · error budget 0.5%</div>
    </section>
  </header>
  <section class="grid" id="grid" aria-label="Six monitoring panels"></section>
  <footer class="foot"><span id="record-count">0 log records</span><span>Auto refresh every 30 seconds</span></footer>
</main>
<script>
const number = (v, digits=0) => v === null || v === undefined ? "—" : Number(v).toLocaleString(undefined,{maximumFractionDigits:digits});
function format(v, unit) {
  if (v === null || v === undefined) return "—";
  if (unit === "ms") return `${number(v)} ms`;
  if (unit === "percent") return `${number(v,2)}%`;
  if (unit === "usd") return `$${number(v,6)}`;
  if (unit === "tokens") return `${number(v)} tokens`;
  if (unit === "requests_per_minute") return `${number(v,2)} req/min`;
  if (unit === "score_0_to_1") return number(v,3);
  if (unit === "count") return number(v);
  return number(v,2);
}
function chartSvg(chart) {
  const values = (chart.values || []).map(Number), width=640, height=120, pad=8;
  if (!values.length) return `<div class="empty-note">No samples in this time range</div>`;
  const max = Math.max(0.000001, ...values, chart.threshold || 0) * 1.12;
  const points = values.map((v,i) => `${pad + i * (width-2*pad)/Math.max(values.length-1,1)},${height-pad-(v/max)*(height-2*pad)}`);
  let markup = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Metric history"><path d="M ${pad} ${height-pad} H ${width-pad}" stroke="#34425b" stroke-width="1" fill="none"/>`;
  if (chart.threshold !== null && chart.threshold !== undefined) {
    const y=height-pad-(chart.threshold/max)*(height-2*pad);
    markup += `<path d="M ${pad} ${y} H ${width-pad}" stroke="#ffb454" stroke-width="1.5" stroke-dasharray="6 5" fill="none"/>`;
  }
  if (chart.kind === "bars") {
    const slot=(width-2*pad)/values.length, bar=Math.max(2,slot*.62);
    values.forEach((v,i)=>{ const x=pad+i*slot+(slot-bar)/2, h=(v/max)*(height-2*pad), y=height-pad-h; markup += `<rect x="${x}" y="${y}" width="${bar}" height="${Math.max(h,1)}" rx="2" fill="#8796ff" opacity=".86"/>`; });
  } else {
    markup += `<polyline points="${points.join(" ")}" fill="none" stroke="#9ba8ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;
    if (values.length === 1) { const [x,y]=points[0].split(","); markup += `<circle cx="${x}" cy="${y}" r="4" fill="#9ba8ff"/>`; }
  }
  return markup + `</svg>`;
}
function render(data) {
  document.title=data.title;
  document.getElementById("title").textContent=data.title;
  document.getElementById("window").textContent=data.window_minutes;
  document.getElementById("record-count").textContent=`${number(data.record_count)} log records in window`;
  document.getElementById("updated").textContent=`Updated ${new Date(data.generated_at).toLocaleString()}`;
  document.getElementById("slo-rate").textContent=data.slo.good_rate_percent === null ? "—" : number(data.slo.good_rate_percent,2);
  document.getElementById("slo-target").textContent=number(data.slo.target_percent,1);
  const status=document.getElementById("slo-status"); status.textContent=data.slo.status;
  status.className="status"+(data.slo.status === "MEETING TARGET" ? "" : data.slo.status === "NO DATA" ? " empty" : " bad");
  const grid=document.getElementById("grid"); grid.replaceChildren();
  data.panels.forEach(p=>{
    const card=document.createElement("article"); card.className="card";
    const stats=(p.stats||[]).map(s=>`<span class="stat"><span>${s.label}</span><strong>${format(s.value,s.unit||p.unit)}</strong></span>`).join("");
    card.innerHTML=`<div class="card-head"><h2>${p.title}</h2><span class="tag">${p.unit.replaceAll("_"," ")}</span></div><div class="main-metric">${format(p.main_value,p.unit)}</div><div class="main-label">${p.main_label}</div><div class="stats">${stats}</div><div class="chart">${chartSvg(p.chart)}</div><div class="threshold"><b>${p.threshold_text}</b></div>`;
    grid.appendChild(card);
  });
}
async function refresh() {
  try { const response=await fetch("/api/dashboard-data",{cache:"no-store"}); if(!response.ok) throw new Error(`HTTP ${response.status}`); render(await response.json()); }
  catch(error) { document.getElementById("updated").textContent=`Dashboard data unavailable: ${error.message}`; }
}
refresh(); setInterval(refresh,30000);
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/dashboard-data":
            body = json.dumps(build_dashboard_data(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        elif route == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        else:
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string: str, *args: Any) -> None:
        return None


def main() -> None:
    from app.cli import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Local six-panel LLMOps dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port} (source: {LOG_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

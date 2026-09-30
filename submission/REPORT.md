# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Thị Hồng Nhung
- **MSSV:** 2A202602557
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/HongNhung-0204/K4-L3-DAY13-NguyenThiHongNhung-2A202602557-Monitoring-LLMOps.git
- **Commit SHA cuối:** b698e111deb782839c1315ac78563bc58ffe7722
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-02557`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Pytest cuối         | `evidence/01-pytest.txt` (25 passed; PNG hiện có chứa banner commit cũ nên không dùng làm evidence cuối)               |
| Log validator       | `evidence/02-log-validator.png`, `evidence/02-log-validator.txt`                                                     |
| Dashboard validator | `evidence/03-dashboard-validator.png`, `evidence/03-dashboard-validator.txt`                                         |
| Structured log      | `evidence/04-structured-log.png`, `evidence/04-structured-log.txt`                                                                                     |
| PII redaction       | `evidence/05-pii-redaction.png`, `evidence/05-pii-redaction.txt`                                                                                      |
| Trace list          | `evidence/06-trace-list.png`, `evidence/06-trace-list.txt`                                                           |
| Trace waterfall     | `evidence/07-trace-waterfall.png`, `evidence/07-trace-waterfall.txt`                                                 |
| Trace metadata      | `evidence/08a-trace-metadata.png`, `evidence/08b-trace-generation.png`, `evidence/08-trace-metadata.txt`             |
| Prompt versions     | `evidence/09-prompt-versions.png`, `evidence/09-prompt-versions.txt`                                                 |
| Prompt rollback     | `evidence/10a-production-v2.png`, `evidence/10b-production-rollback-v1.png`, `evidence/10-prompt-rollback.txt`       |
| Dashboard runtime   | `evidence/11-dashboard-overview.png`                                                                                 |
| Incident metric     | `evidence/12-incident-metric.png`, `evidence/12-incident-metric.txt` (historical metric snapshot)                    |
| Incident log        | `evidence/13-incident-log.png`, `evidence/13-incident-log.txt` (sanitized fields)                                    |
| Incident trace      | `evidence/14-incident-trace.png`, `evidence/14-incident-trace.txt` (Langfuse trace and span metadata)                 |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline     | Kết quả cuối                  | Nhận xét                                                                         |
| ----------------------- | ------------ | ----------------------------- | -------------------------------------------------------------------------------- |
| `validate_logs.py`      | 30/100       | 100/100                       | CP2: 77 records/28 IDs; latest evidence: 90 records/35 IDs; 0 PII leak            |
| `validate_dashboard.py` | —            | 6/6 panel                     | Contract đạt; dashboard runtime có đủ dữ liệu, time range, đơn vị và threshold   |
| `pytest`                | —            | 25 passed                     | Full test suite sau CP2                                                          |
| Số traces hợp lệ        | —            | 10 workload + 3 prompt traces | Cả 10 workload trace được kiểm tra trong project cá nhân qua Observations API v2 |
| Số PII leak             | 0            | 0                             | Latest validator evidence: 90 log records, 35 correlation IDs; không thấy PII thô |
| Latency P95 / TTFT P95  | 1288 / 50 ms | 1288 / 50 ms                  | Baseline CP2, cửa sổ dashboard 60 phút; CP3 incident riêng ở mục 7               |
| Retrieval success rate  | —            | 100%                          | 29 response; 0 request failure                                                   |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ, nhận `x-request-id` hợp lệ dạng `req-<8 hex>` hoặc sinh ID mới, bind ID vào structlog context và trả lại trong response header. `app.main` truyền cùng ID vào `LabAgent.run`, nơi ID đã được đưa vào metadata trace.
- **Các metadata được ghi vào structured log:** `user_id_hash` (SHA-256 rút gọn), `session_id`, `feature`, `model` và `env` được bind trước `request_received`; middleware bind `correlation_id` trước khi xử lý request.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` chạy đệ quy sau khi format exception và trước JSONL writer/JSON renderer; log values được scrub theo pattern email, điện thoại VN, CCCD và thẻ thanh toán.
- **Cách kiểm chứng kết quả:** CP1 `tests/test_pii.py` có 5 test pass; load test gửi 10 request, cả 10 trả HTTP 200. CP1 validator đạt 100/100 với 29 log records và 13 correlation ID. Sau workload CP2, validator đạt 100/100 với 77 records, 28 correlation ID, không thiếu trường bắt buộc/context và 0 PII leak. Response được kiểm tra với ID hợp lệ truyền vào, ID không hợp lệ được thay mới, cùng header `x-response-time-ms`. Xem `evidence/04-structured-log.png` và `evidence/05-pii-redaction.png` (log trích nguyên văn: các file `.txt` cùng tên).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** 10 request từ `scripts/load_test.py --concurrency 5` tạo 10 trace riêng trong project `day13-k4-l3b-02557`; cả 10 trace đều được đối chiếu correlation ID, cây observation và prompt v1 bằng Langfuse Observations API v2. Danh sách nằm ở `evidence/06-trace-list.txt` và `evidence/cp2-loadtest-traces.json`.
- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` là root; `retrieval` (RETRIEVER) và `llm-generation` (GENERATION) là child. Generation có model, input/output token usage, cost và liên kết prompt managed. Xem `evidence/07-trace-waterfall.txt`.
- **Cách nối trace với log:** Cùng `correlation_id` được ghi trong structured log và metadata trace. Ảnh waterfall request 04 dùng `req-d78537bc`; metadata/token/cost cùng trace ID được ghi ở `evidence/08-trace-metadata.txt`.
- **Prompt name:** `day13-chat`, text prompt với các biến `feature`, `docs`, `message`.
- **Version/label baseline:** v1, label `baseline`; ban đầu cũng mang `production`.
- **Version/label candidate:** v2, label `candidate`.
- **Trace ID của mỗi version:** baseline v1 `936374d44cad57d6051a957350b6e29e`; candidate v2 `f3af17941f7941783ac9d0f98e19336c`. Cả hai dùng cùng input; link trace nằm trong `evidence/cp2-prompt-traces.json`.
- **Cách promote và rollback `production`:** chuyển `production` sang v2 rồi gửi request, trace promote `67b36613e10ef1c74a0739925b8d57b1`; sau đó chuyển `production` về v1. Đã xác minh trạng thái hiện tại là production v1; xem `evidence/09-prompt-versions.txt` và `evidence/10-prompt-rollback.txt`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard runtime đọc `data/logs.jsonl`, hiển thị 60 phút gần nhất và refresh 30 giây: latency/TTFT, traffic, error/retrieval success, cost, tokens và quality. Ảnh `evidence/11-dashboard-overview.png` cho thấy cả sáu panel cùng số liệu.
- **SLO và lý do chọn:** 99.5% request phải trả lời thành công trong tối đa 3 giây, theo cửa sổ 28 ngày; mục tiêu giữ P95 dưới ngưỡng dễ quan sát và phản ứng.
- **Cách tính error budget:** 0.5% request không đạt SLI; tối đa 50 trên 10,000 request trong cửa sổ 28 ngày. Workload hiện tại đạt 100% SLI trong mẫu 29 request, không đại diện phân phối production.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` >2,000 ms trong 5 phút (cảnh báo sớm hơn SLO 3,000 ms); `ElevatedRequestErrorRate` >2% trong 3 phút; `LowRetrievalSuccess` <90% trong 5 phút. Cả ba gửi Slack `#k4-l3b-alerts`, runbook tại `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4).
- **Khoảng thời gian điều tra:** 2026-09-30 05:44:40–05:44:54 UTC (12:44:40–12:44:54 giờ Việt Nam). Dashboard snapshot dùng cửa sổ 60 phút kết thúc lúc 05:44:54 UTC.
- **Triệu chứng từ metrics:** P95 latency 2,654 ms và TTFT P95 50 ms trên 5 response trong cửa sổ incident; P95 vượt ngưỡng challenge 2,000 ms nhưng vẫn thấp hơn SLO tổng thể 3,000 ms. `scripts/load_test.py` ghi nhận thời gian client 7,991–13,307 ms cho batch đồng thời. Rule 3,000 ms cũ không bắt được metric server này, và `response_sent.latency_ms` không tính thời gian chờ trước khi agent bắt đầu chạy.
- **Log line và correlation ID liên quan:** `response_sent` lúc `2026-09-30T05:44:42.979636Z`, `correlation_id=req-b101ea1f`, `feature=monitoring`, `latency_ms=2653`, `trace_id=d4ca0fcf36658f98969e1ce213cab092` (đã loại payload khỏi evidence).
- **Trace ID và span gây ảnh hưởng:** `d4ca0fcf36658f98969e1ce213cab092`; root `lab-agent-run` 2,657 ms, child `retrieval` 2,501 ms, `llm-generation` 151 ms. Correlation ID trong trace trùng log.
- **Root cause:** incident `rag_slow` làm `retrieve()` chờ 2.5 giây; trace định vị độ trễ ở retrieval, còn generation chỉ 151 ms. Tác động bị khuếch đại vì route `async` gọi pipeline đồng bộ trực tiếp, khiến batch đồng thời phải chờ event loop.
- **Fix action:** tắt incident qua `scripts/inject_incident.py --disable`; `/health` xác nhận `rag_slow=false` và các incident khác cũng false. Chuyển `agent.run` sang `run_in_threadpool` trong `app/main.py` để không chặn event loop.
- **Preventive measure:** hạ ngưỡng cảnh báo sớm `HighLatencyP95` từ 3,000 xuống 2,000 ms trong 5 phút tại `config/alert_rules.yaml`; cập nhật runbook `docs/alerts.md`. SLO tổng thể vẫn là 99.5% trong 28 ngày với latency tối đa 3,000 ms. Đo và ghi thêm end-to-end request duration để dashboard tính cả thời gian chờ; burst thử nghiệm ngắn hơn 5 phút nên không kết luận alert đã kích hoạt.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Chọn SLO 99.5% trong 28 ngày với ngưỡng latency 3,000 ms; error budget 0.5% diễn giải được thành tối đa 50 request trên 10,000.
- **Một lỗi/blocker đã gặp:** Dữ liệu trace ở project Langfuse mới không đọc được qua API trace cũ; server trả HTTP 410.
- **Cách tìm nguyên nhân và xử lý:** Chuyển xác minh sang Langfuse Observations API v2; đọc được trace tree, metadata, prompt link và token/cost.
- **Cách hiểu luồng Metrics → Logs → Traces:** Dashboard tổng hợp log JSONL; lấy correlation ID từ log để tìm trace và child span tương ứng.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Mỗi generation chỉ rõ prompt version và chi phí; label production có thể promote/rollback độc lập với code.
- **Điều quan trọng nhất đã học:** Cần xác minh dữ liệu trace thực tế qua API/UI, không chỉ dựa trên metadata hoặc unit test.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** CP3 PNG/TXT 12–14 hiện đã có. Ảnh 12 chụp snapshot metrics lịch sử vì dashboard live mặc định đã cuộn khỏi cửa sổ 60 phút; ảnh 13 hơi cắt cuối dòng nên TXT đi kèm là bản đầy đủ. Ảnh 01 có banner commit trước khi đồng bộ upstream; dùng TXT làm evidence pytest cho tới khi chụp lại trên trạng thái cuối.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence 12–14 (PNG/TXT) nối được metric → log → trace qua `req-b101ea1f`.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README (chạy lại checks trên trạng thái cuối trước khi commit).
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

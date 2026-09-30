# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- **Tên:** `HighLatencyP95`. **Severity:** warning; **duration:** 5m; **Slack:** `#k4-l3b-alerts`; **owner:** `student-02557`.
- **SLI/SLO:** P95 của `response_sent.latency_ms`; cảnh báo sớm khi P95 > 2000ms trong 5 phút. SLO tổng thể vẫn yêu cầu latency <= 3000ms.
- **Ảnh hưởng:** người dùng chờ lâu trước khi nhận câu trả lời.
- **Kiểm tra:** (1) xem panel latency và xác nhận time range/P95/P99; (2) lọc `response_sent` trong `data/logs.jsonl`, ghi lại `correlation_id`; (3) mở trace tương ứng, so thời gian retrieval và generation cùng `prompt_version`.
- **Mitigation:** nếu retrieval chiếm thời gian, tắt practice scenario hoặc phục hồi cấu hình retrieval; nếu generation/prompt thay đổi cùng thời điểm, rollback label `production` về version đã ổn định. Theo dõi P95 thêm 5 phút.

## Alert 2

- **Tên:** `ElevatedRequestErrorRate`. **Severity:** critical; **duration:** 3m; **Slack:** `#k4-l3b-alerts`; **owner:** `student-02557`.
- **SLI/SLO:** tỷ lệ `request_failed` trên `request_received`; bắn khi vượt 2% trong 3 phút.
- **Ảnh hưởng:** một phần request không trả được câu trả lời.
- **Kiểm tra:** (1) xem error rate và breakdown theo `error_type`; (2) lọc `request_failed`, `tool_success=false` và lấy `correlation_id`; (3) mở trace cùng ID để xem observation cuối cùng thành công và lỗi.
- **Mitigation:** tắt incident practice đang gây lỗi hoặc khôi phục dependency/configuration gần nhất đã đổi; giữ lại log và trace ID để xác nhận lỗi giảm dưới 2%.

## Alert 3

- **Tên:** `LowRetrievalSuccess`. **Severity:** warning; **duration:** 5m; **Slack:** `#k4-l3b-alerts`; **owner:** `student-02557`.
- **SLI/SLO:** tỷ lệ tool call retrieval thành công; bắn khi thấp hơn 90% trong 5 phút.
- **Ảnh hưởng:** câu trả lời có thể thiếu ngữ cảnh đã truy xuất.
- **Kiểm tra:** (1) xem panel errors và retrieval success; (2) lọc log theo `tool_name=retrieval` và `tool_success`; (3) mở trace để kiểm tra observation `retrieval`, `doc_count` và lỗi liên quan.
- **Mitigation:** tắt practice scenario gây lỗi, khôi phục nguồn retrieval đã hoạt động và chạy lại sample query. Xác nhận success rate vượt 90% liên tục 5 phút.

# Evidence cá nhân

Đặt ảnh hoặc output text dùng để chấm vào thư mục này. Danh sách đầy đủ xem tại [docs/SUBMISSION.md](../../docs/SUBMISSION.md).

Tên file gợi ý:

```text
01-pytest.png
02-log-validator.png
03-dashboard-validator.png
04-structured-log.png
05-pii-redaction.png
06-trace-list.png
07-trace-waterfall.png
08a-trace-metadata.png, 08b-trace-generation.png
09-prompt-versions.png
10a-production-v2.png, 10b-production-rollback-v1.png
11-dashboard-overview.png
12-incident-metric.png
13-incident-log.png
14-incident-trace.png
```

Có thể dùng `.txt` cho output của tests/validators. Có thể tách dashboard thành nhiều ảnh nếu một ảnh không đọc rõ.

Ảnh `04`, `05`, `13` lấy từ terminal hoặc `data/logs.jsonl`. Ảnh `06`–`10`, `14` lấy từ project Langfuse cá nhân `day13-k4-l3b-<MSSV>` và nên nhìn thấy tên project. Không mở/chụp trang API Keys.

CP2 đã lưu thêm các kết quả xác minh trực tiếp từ project Langfuse cá nhân:

- `06-trace-list.txt` và `cp2-loadtest-traces.json`: 10 trace từ workload, đối chiếu correlation ID, observations, prompt version, token và cost.
- `07-trace-waterfall.txt`, `08-trace-metadata.txt`, `09-prompt-versions.txt`, `10-prompt-rollback.txt`: cấu trúc trace và trạng thái prompt đã xác minh qua API.
- `cp2-prompt-traces.json`: trace link cho cùng input với baseline, candidate và production sau promote.
- `11-dashboard-overview.png`: ảnh runtime của dashboard local.
- `12-incident-metric.png/.txt`, `13-incident-log.png/.txt`, `14-incident-trace.png/.txt`: bằng chứng CP3 đã scrub, nối cùng metric → correlation ID → trace; ảnh 12 là snapshot metrics lịch sử vì dashboard mặc định đã cuộn khỏi cửa sổ 60 phút.

Các file TXT/JSON là dữ liệu đối chiếu và bổ sung cho ảnh UI. Ảnh CP2 06–10 đã có trong thư mục; với ảnh Langfuse, mở trace URL trong JSON sau khi đăng nhập project cá nhân và để tên project cùng nội dung tương ứng hiện rõ.

Ảnh CP3 12–14 đã có. Ảnh 13 có thể chụp lại với cửa sổ rộng hơn để thấy trọn dòng log; file TXT vẫn giữ dòng đầy đủ. Không chụp raw challenge input/output.

Từ `submission/REPORT.md`, dẫn ảnh bằng đường dẫn tương đối:

```markdown
![Trace waterfall](evidence/07-trace-waterfall.png)
```

Không commit secret, API key, PII thô hoặc evidence của học viên/lớp khác.

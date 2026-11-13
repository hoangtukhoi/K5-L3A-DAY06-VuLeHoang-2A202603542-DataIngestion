# Benchmark

- `questions.jsonl`: 24 câu (15 dev / 9 test) trên corpus `starter/data/root_data.pdf`.
- Kiểm tra: `cd starter && python scripts/verify_benchmark.py` (đếm số câu, kiểm tra trang gold, filter và evidence).

## Cách chia dev/test (chốt trước khi chạy retrieval)

- **Dev** = câu có evidence ở chương 1–9 (D01–D15). **Test** = chương 10–13 (T01–T09).
- Chia theo chương/chủ đề để giảm rò rỉ: kiến thức test (static, Singleton, final, ngoại lệ, chuỗi hóa, collection) là chủ đề khác dev.
- Nguy cơ rò rỉ còn lại: các chương sau tham chiếu lại khái niệm ở chương trước (ví dụ `==` ở ch.2 và ch.13; sao chép đối tượng ở ch.4 và ch.9), và cùng một giáo trình/giọng văn.
- Đã kiểm chứng: câu hỏi và evidence do tác giả soạn từ việc đọc trực tiếp các trang gold, chưa chạy retrieval trên bất kỳ câu nào. Không điều chỉnh chiến lược theo test.

## Filter

- 6 câu có filter `{"chapter": N}` (dev: D05, D11, D15; test: T01, T03, T09).
- Giá trị chương được xem là **ngữ cảnh người dùng cung cấp trước khi truy xuất** (giả định: người dùng đang đọc chương đó); không lấy từ gold ngoài chương.
- Các câu filter được chọn vì chủ đề xuất hiện ở nhiều chương (phép gán/sao chép tham chiếu, overload, `==`, static/final), nên filter có tác dụng phân biệt.
- Cấu hình C chỉ áp filter cho 6 câu này; 18 câu còn lại chạy không filter.

## Quy ước

- `gold_page` = số trang PDF (trùng số trang in). Mỗi câu chỉ có 1 trang gold; evidence nằm trọn trong một trang.
- `evidence_quote` được so khớp bỏ qua khoảng trắng (PDF có khoảng trắng thừa trong chữ tiếng Việt).
- Loại câu (`type`): direct, paraphrase, condition, filter. Chỉ dùng để phân tích lỗi, không có tỷ lệ cố định.

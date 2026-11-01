**Đề xuất phát triển JSON Mapper — dựa trên kiểm thử 01–02/11/2026**

Mục tiêu gần nhất là giúp người dùng hoàn thành một phiên mapping, hiểu lỗi và giữ được công việc đang làm. Engine đã vượt qua 82 test hiện hữu và các kịch bản UI được thử cho kết quả đúng; ưu tiên tiếp theo nên tập trung vào trải nghiệm desktop và bảo vệ phiên. Chi tiết bằng chứng nằm trong [báo cáo](./REPORT.md).

P1 = làm trước đợt phát hành tiếp theo; P2 = đợt tiếp theo; P3 = cải thiện nhỏ khi chạm vào khu vực liên quan. Ước lượng dưới đây là ngày công kỹ thuật tham khảo, gồm triển khai và kiểm chứng trên Windows, chưa phải cam kết tiến độ.

| Mã | Ưu tiên | Đề xuất | Giá trị và phạm vi | Ước lượng |
| --- | --- | --- | --- | --- |
| DEV-01 | P1 | Bố cục thích ứng theo không gian cửa sổ | Giữ toolbar, options, status luôn thấy; vùng dữ liệu co giãn/cuộn; sửa F01 | 1–2 ngày |
| DEV-02 | P1 | Theo dõi thay đổi và nhắc lưu | Dirty-state cho nguồn/mẫu/rule; Lưu / Bỏ thay đổi / Hủy khi đóng hoặc thay phiên | 2–3 ngày |
| DEV-03 | P2 | Bản nháp khôi phục và lưu phiên mapper | Lưu nguồn + cấu hình cho mapper; phục hồi sau lần đóng bất thường; người dùng chủ động quản lý bản nháp | 2–4 ngày |
| DEV-04 | P2 | Đồng bộ trạng thái parse/validation | Xóa nhãn cũ khi sửa/undo/nạp; đánh dấu kết quả kiểm tra custom đã hết hiệu lực; sửa F02/F05 | 0.5–1 ngày |
| DEV-05 | P2 | Bảng lỗi có thể thao tác | Xuống dòng thông báo; rule, record, source/target path riêng; chọn lỗi để tới rule/editor | 1–2 ngày |
| DEV-06 | P2 | Chọn path theo ngữ cảnh | Hỗ trợ source_root/each, tìm kiếm field, preview value/type, chèn trực tiếp vào rule | 3–5 ngày |
| DEV-07 | P2 | Undo/redo cho cấu hình và nguồn | Khôi phục xóa/đổi thứ tự rule, bỏ nguồn, thay mẫu; tách khỏi undo văn bản | 2–4 ngày |
| DEV-08 | P2 | Kiểm thử UI lặp lại và accessibility | Luồng chuột/bàn phím thật, screenshot ở các kích thước/DPI; audit tên/role/focus điều khiển | 2–4 ngày ban đầu |
| DEV-09 | P3 | Nhập nguồn và form rõ trạng thái | Alias sai được sửa tại chỗ, không chọn file lại; vô hiệu ô không áp dụng; hiển thị tên file đang dùng | 1–2 ngày |
| DEV-10 | P3 | Hướng dẫn chạy và trợ giúp tại chỗ | Bỏ đường dẫn máy cũ; hướng dẫn prefix/path/transforms và phím tắt ngay trong ứng dụng | 0.5–1 ngày |

**DEV-01 — tiêu chí nghiệm thu.** Kiểm tra cả mapper/composer ở 1100×700, 1366×768 và màn hình Full HD; chạy ở 100%, 125%, 150% DPI. Tất cả nút thao tác chính, Thiếu field/Ghi chồng và trạng thái phải nhìn thấy hoặc tiếp cận bằng một vùng cuộn rõ ràng. Không cắt nút lưu/hủy trong hộp thoại. Mở/nạp/chuyển đổi/xuất có phản hồi đọc được. Các kích thước/DPI này là mục tiêu nghiệm thu đề xuất, chưa được kiểm chứng đầy đủ trong đợt hiện tại.

**DEV-02/03 — tiêu chí nghiệm thu.** Chỉnh nguồn, mẫu, rule, thứ tự, alias hoặc danh sách nguồn phải đánh dấu phiên đã đổi; xem preview không tự làm sạch dirty-state. Đóng, bấm Ví dụ, nạp nguồn/rule/phiên hoặc dùng nguồn khác làm mẫu phải bảo vệ nội dung chưa lưu khi thao tác có thay thế dữ liệu. Hủy giữ nguyên trạng thái; Lưu thất bại không được đóng cửa sổ; lưu thành công cập nhật bản hiện hành. Mapper lưu được phiên đầy đủ. Khôi phục bản nháp có thời gian, tên phiên và lựa chọn mở/bỏ; không tự ghi lên file nguồn.

**DEV-04 — tiêu chí nghiệm thu.** Tái hiện JSON trùng key → format lỗi → undo → F5 thành công: không còn nhãn “JSON lỗi” của phiên bản cũ. Nạp file hợp lệ cũng xóa/đặt lại trạng thái. Custom rule sau Kiểm tra mà có thay đổi phải báo cần kiểm tra lại; nút Lưu vẫn kiểm tra lại toàn bộ cấu hình như hiện nay.

**DEV-05 — tiêu chí nghiệm thu.** Với lỗi thiếu A và lỗi parse mẫu, toàn bộ thông báo phải đọc được không cần cuộn ngang. Có thể chọn lỗi để tới đúng rule; lỗi parse chỉ rõ editor nào và line/column. Giữ bản báo cáo JSON máy đọc được bên cạnh phần trình bày cho người dùng. Không hiện preview cũ như kết quả của lượt chạy lỗi.

**DEV-06 — tiêu chí nghiệm thu.** Ở document/$, chọn customer.name sinh path đầy đủ phù hợp. Ở each/orders, chọn id sinh id của bản ghi hiện tại, không phải $.orders[*].id. Với composer, chọn nguồn và kiểu value/field phải sinh prefix đúng; literal key có dấu chấm/Unicode được escape đúng. Nguồn thiếu/field không hợp lệ có giải thích ngay tại ô. Không tự suy đoán hoặc áp mapping khi người dùng chưa chọn.

**DEV-07 — tiêu chí nghiệm thu.** Undo/redo khôi phục đúng thao tác xóa một/nhóm rule, đổi thứ tự, bỏ nguồn và thay mẫu; toàn bộ cấu hình phải nhất quán. Mọi thao tác undo/redo liên quan dữ liệu đều vô hiệu preview/export đến khi chạy lại. Có giới hạn bộ nhớ hợp lý vì phiên chứa toàn bộ JSON.

**DEV-08 — tiêu chí nghiệm thu.** Lưu một bộ smoke test desktop tách khỏi test callback Tk. Tối thiểu gồm mở app, nhập Unicode, thêm/sửa/xóa/chọn nhiều rule, source file tốt/xấu, format/undo, xuất rồi đối chiếu, composer ba nguồn, lưu/nạp phiên, alias trùng, mẫu lỗi, chặn ghi đè nguồn và đóng khi chưa lưu. Đánh giá ảnh thực tế và khả năng tiếp cận điều khiển; không chỉ kiểm tra tọa độ widget bằng code. Ghi rõ những ca không chạy được do môi trường. Test hardlink phải có chính sách skip nhất quán khi filesystem/sandbox không hỗ trợ.

**DEV-09/10 — tiêu chí nghiệm thu.** Alias A trùng giữ nguyên hộp alias và file đã chọn, đưa gợi ý tên duy nhất. Form from/value/delete chỉ bật các ô có tác dụng. File/phiên hiện tại và trạng thái chưa lưu nhìn thấy rõ. Hướng dẫn start.cmd chạy được từ mọi thư mục checkout; các ví dụ path trong README không phụ thuộc một máy cụ thể.

**Lộ trình đề xuất**

| Đợt | Phạm vi | Điều kiện hoàn tất |
| --- | --- | --- |
| 1 — ổn định sử dụng | DEV-01, DEV-02, DEV-04, DEV-10 | Đọc được mọi điều khiển/trạng thái, không mất thay đổi mà không được nhắc, lỗi hiển thị đồng bộ; 82 test hiện hữu vẫn đạt |
| 2 — thao tác nhanh và phục hồi | DEV-03, DEV-05, DEV-06, DEV-07, DEV-09 | Người dùng tạo mapping qua picker, tìm/sửa lỗi và phục hồi phiên bằng UI |
| Xuyên suốt | DEV-08 | Mỗi thay đổi UI có ca desktop phù hợp và bằng chứng ở các cấu hình hiển thị mục tiêu |

**Các hướng mở rộng sau khi ổn định**

| Hướng phát triển | Điều kiện trước khi làm | Tiêu chí đầu ra |
| --- | --- | --- |
| Validate JSON Schema đích | Chọn draft/schema và quy tắc strictness | Lỗi schema chỉ đúng path; không đánh đồng mapping thành công với hợp lệ nghiệp vụ |
| Join nhiều nguồn theo khóa | Chốt inner/left/full, khóa trùng, null, thiếu và thứ tự kết quả | Ca kiểm thử xác định rõ cardinality, báo bản ghi không ghép được, kết quả lặp lại ổn định |
| Chạy nền với progress/cancel | Đo tải thực tế và giới hạn RAM | UI vẫn phản hồi, hủy không để lại output dở dang, báo tiến độ có ý nghĩa |
| JSONL/streaming và batch file | Có nhu cầu về kích thước/khối lượng và contract từng dòng | Chính sách lỗi từng record rõ; bảo toàn thứ tự; báo cáo tổng hợp và ghi file an toàn |
| Báo cáo diff/coverage mapping | Định nghĩa field được giữ, tạo, đổi, bỏ | Người dùng biết dữ liệu nào bị loại khi base=empty và xem mẫu trước/sau |
| Đóng gói bản desktop | Chọn cơ chế phân phối/cập nhật | Người dùng chạy được không cần tự cài Python; có version, hướng dẫn và smoke test trên máy sạch |

Các mở rộng này hiện nằm ngoài phạm vi đã cam kết của công cụ. Chúng là đề xuất có điều kiện, không được tính là lỗi của bản hiện tại. Nên chọn theo nhu cầu sử dụng thực tế trước khi ước lượng chi tiết.

**Phạm vi bàn giao đợt QA:** báo cáo, ma trận kiểm thử, ảnh, log, fixture và file xuất nằm trong qa/2026-11-01/. Mã ứng dụng được giữ nguyên để các phát hiện còn tái hiện được trên commit đã ghi.

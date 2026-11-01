**Báo cáo kiểm thử JSON Mapper bằng điều khiển màn hình — 01–02/11/2026 (Asia/Saigon)**

Bản kiểm thử: commit **8d015a7**, thư mục D:/Tools/json-mapper. Phạm vi gồm cửa sổ mapping một nguồn, cửa sổ ghép nhiều JSON và các editor/hộp thoại chung. Không sửa mã nguồn ứng dụng trong đợt này.

**Kết quả:** 38 kịch bản chức năng UI đạt; ghi nhận 2 lỗi giao diện tái hiện được và 3 quan sát UX trong ma trận. Bộ kiểm thử hiện hữu đạt **82/82**, không skip ở lần chạy cuối. Kết quả xuất composer khớp hoàn toàn với JSON kỳ vọng. Không phát hiện kết quả mapping sai trong những ca đã chạy; kết luận này không bao hàm mọi dữ liệu hay mọi tổ hợp cấu hình.

Kiểm tra UI thực hiện bằng chuột, bàn phím và hộp chọn/lưu file thật. Các test unittest là bằng chứng bổ trợ, được ghi tách khỏi kết quả thao tác màn hình. Dữ liệu dùng là examples/ và fixture giả trong thư mục QA. Có 24 ảnh bằng chứng; không phải mỗi thao tác đều được lưu thành ảnh riêng.

Môi trường: Windows, Python 3.14, Tk 8.6. Ảnh cửa sổ mặc định khoảng 1835–1847 × 1007; ảnh maximize 1920 × 1020. Không thay đổi hoặc đo riêng DPI hệ thống, vì vậy chưa kết luận về tất cả mức DPI. Các lần nhập/clipboard và test đầu tiên bị ảnh hưởng bởi sandbox cùng thao tác đồng thời của người dùng; đã chuyển sang bản desktop bình thường và chạy lại các ca cần thiết. Lỗi thư mục tạm/hardlink trong các log đầu là lỗi môi trường, không được tính là lỗi sản phẩm.

**Bằng chứng máy đọc được và kết quả xuất**

- [Ma trận chi tiết JSON](./test-matrix.json).
- [Log kiểm thử cuối: 82 tests, OK](./automated-tests-final.log).
- [Kết quả mapper](./mapper-output.json) và [20 rule đã lưu qua UI](./mapper.rules.json).
- [Kết quả composer](./composer-output.json) và [phiên A/B/C đã lưu qua UI](./composer.session.json).
- [Đề xuất phát triển có tiêu chí nghiệm thu](./DEVELOPMENT_PROPOSAL.md).

**Các phát hiện cần xử lý**

**F01 — P1: Bố cục che các điều khiển quan trọng.** Mở composer, nạp ví dụ, quan sát tab Rule và tab Mẫu ở kích thước mặc định rồi maximize. Các lựa chọn Thiếu field/Ghi chồng và thanh trạng thái không nằm trong vùng thấy được. Mapper cũng cắt phần hướng dẫn/trạng thái phía dưới. Người dùng không thấy xác nhận copy/lưu/xuất và khó đổi chính sách xung đột bằng UI. Có thể dùng cấu hình JSON nâng cao làm giải pháp tạm. [Ảnh mặc định](./screenshots/12-composer-demo.png), [ảnh maximize](./screenshots/18-composer-rule-options-clipped.png). Vùng mã cần xem: [bố cục composer](../../composer_app.py#L95), [options](../../composer_app.py#L136), [status composer](../../composer_app.py#L153), [status mapper](../../app.py#L256). Cần kiểm tra phân bổ chiều cao trước khi chốt nguyên nhân; ảnh đã xác nhận biểu hiện.

**F02 — P2: Nhãn “JSON lỗi” tồn tại sau khi JSON đã hợp lệ.** Trong mapper, nhập {"x":1,"x":2}, bấm định dạng; Ctrl+Z rồi F5. Preview thành công nhưng nhãn đỏ vẫn còn. Nạp lại file nguồn hợp lệ cũng không xóa nhãn; định dạng hợp lệ lại mới xóa. Đây là lỗi trạng thái hiển thị, không phải engine parse sai. [Ảnh tái hiện](./screenshots/08-stale-json-error-after-success.png). Đối chiếu [JsonEditor.format_json](../../json_editor.py#L43) và [source_changed](../../app.py#L266): trạng thái nhãn chỉ được cập nhật trong thao tác format.

**F03 — P1, thiếu cơ chế bảo vệ phiên: Đóng khi chưa lưu không có nhắc nhở.** Đóng composer sau khi thay đổi mẫu/rule và đóng mapper sau khi thay nguồn đều kết thúc cửa sổ ngay. Phiên đã lưu vẫn là bản cũ; nội dung chưa lưu không được bảo vệ. README đã công bố không tự lưu, nên đây là khoảng trống sản phẩm, không phải lỗi trái tài liệu. Chế độ mapper còn chưa có chức năng lưu toàn bộ nguồn + rule thành một phiên như composer. Đề nghị ưu tiên dirty-state, nhắc lưu và khôi phục bản nháp.

**F04 — P2, UX: Nội dung lỗi dài bị cắt ngang.** Bỏ A trong composer rồi F5: phần “Chưa nạp nguồn…” bị cắt ở mép phải, muốn biết đầy đủ phải cuộn ngang. Lỗi parse mẫu cũng tương tự. [Ảnh](./screenshots/13-missing-source-error-clipped.png). JSON cần cuộn ngang có thể giữ nguyên; thông báo lỗi nên dùng vùng riêng có xuống dòng, tên rule/path rõ và nút đi tới nơi sửa.

**F05 — P3: Kết quả kiểm tra custom rule bị cũ sau khi sửa nội dung.** Sau nhóm bad..path bị từ chối, thay nội dung bằng nhóm hợp lệ và định dạng, thông báo đỏ cũ vẫn còn đến lần Kiểm tra tiếp theo. [CustomRuleDialog](../../custom_rules.py#L39) không đặt lại feedback khi editor thay đổi. Việc lưu luôn kiểm tra lại nên chưa thấy lưu rule sai; vấn đề là người dùng không biết thông báo đang ứng với phiên bản nội dung nào. Đổi sang “Nội dung đã đổi — cần kiểm tra lại” khi có sửa.

**F06 — P3, tài liệu: Hướng dẫn mở dùng đường dẫn cũ.** [README](../../README.md#L6) và ví dụ Set-Location còn trỏ D:/HelloWorld/AutoTool/json-mapper, khác thư mục hiện tại D:/Tools/json-mapper. start.cmd đã chuyển theo vị trí của chính nó. Nên dùng hướng dẫn đường dẫn tương đối hoặc ghi rõ đường dẫn chỉ là ví dụ.

**F07 — P2, UX: Path được copy chưa theo gốc mapping hiện tại.** Khi each/source_root=orders, danh sách Path nguồn vẫn hiển thị $.orders[*].id… trong khi rule cần id/amount của từng bản ghi. README có giải thích giới hạn này; UI chỉ dẫn chưa đủ gần thao tác. [Ảnh](./screenshots/10-each-output-root.png). Nên có picker theo ngữ cảnh và hiển thị gốc hiện hành cạnh ô path.

Ngoài các phát hiện trên, cây accessibility Windows trong lần thử chủ yếu trả về pane không có tên điều khiển. Cần audit khả năng dùng bằng bàn phím/screen reader và độ ổn định của automation. Đây là quan sát từ công cụ UIA; chưa thực hiện đánh giá đầy đủ bằng screen reader.

**Ma trận kiểm tra trực tiếp**

PASS nghĩa là đạt kết quả được nêu ở đúng ca đó; FAIL_UI là lỗi hiển thị; UX_GAP là hành vi hiện tại đã quan sát nhưng cần cải thiện. Các bước cụ thể cho từng ca nằm trong test-matrix.json.

| Mã | Tính năng / ca kiểm tra | Kết quả thực tế | Trạng thái | Bằng chứng |
| --- | --- | --- | --- | --- |
| UI-01 | Khởi động mapper | Có JSON nguồn, 9 rule và preview hợp lệ. | PASS | [Ảnh](./screenshots/01-mapper-demo-report.png) |
| UI-02 | Chuyển đổi và báo cáo | Ví dụ ghi 12 giá trị, 1 default, 0 skip. | PASS | [Ảnh](./screenshots/01-mapper-demo-report.png) |
| UI-03 | 14 phép biến đổi | copy/string/integer/number/boolean/trim/lower/upper/split/join/replace/lookup/parse_json/json_string cho kết quả đúng. | PASS | [Ảnh](./screenshots/06-all-transforms-output.png) |
| UI-04 | Từ chối nhóm custom có lỗi | Từ chối toàn nhóm, giữ nội dung nhập và preview cũ. | PASS | [Ảnh](./screenshots/04-custom-batch-rejected.png) |
| UI-05 | Thêm nhóm custom hợp lệ | Kiểm tra báo 11 rule hợp lệ; thêm thành công; preview cũ bị xóa trước khi chạy lại. | PASS | [Ảnh](./screenshots/05-custom-valid-11-rules.png) |
| UI-06 | Thêm rule bằng form | Rule được thêm; chạy thành công. | PASS | [Ảnh](./screenshots/09-copy-path-add-form.png) |
| UI-07 | Sửa rule bằng form | Bảng cập nhật giá trị; preview bị vô hiệu hóa. | PASS | Quan sát trực tiếp |
| UI-08 | Đổi thứ tự rule | Hàng dịch chuyển lên/xuống đúng một vị trí. | PASS | Quan sát trực tiếp |
| UI-09 | Xóa rule | Hàng biến mất; nút thao tác khóa khi không còn chọn hàng. | PASS | Quan sát trực tiếp |
| UI-10 | Trạng thái nút theo lựa chọn | Sửa/Xóa/↑/↓/Sửa JSON bật hoặc khóa theo lựa chọn đơn. | PASS | Quan sát trực tiếp |
| UI-11 | Lưu và nạp rule | Khôi phục 20 rule trước khi sửa/xóa, chạy thành công. | PASS | Quan sát trực tiếp |
| UI-12 | Xuất JSON một nguồn | File UTF-8 chứa Unicode và đúng các giá trị QA. | PASS | [Ảnh](./screenshots/06-all-transforms-output.png) |
| UI-13 | JSON trùng key | Báo key x bị lặp; không xuất được kết quả. | PASS | [Ảnh](./screenshots/07-duplicate-key-blocked.png) |
| UI-14 | Undo dữ liệu nguồn | Nguồn mẫu và preview được khôi phục; nhãn lỗi còn tồn tại được ghi riêng tại F02. | PASS | [Ảnh](./screenshots/08-stale-json-error-after-success.png) |
| UI-15 | Quét/copy path | Clipboard chứa đúng path đầy đủ. | PASS | [Ảnh](./screenshots/09-copy-path-add-form.png) |
| UI-16 | Cấu hình nâng cao và each | Có hai bản ghi đúng code/total/currency trong payload.rows; các ô cấu hình đồng bộ. | PASS | [Ảnh](./screenshots/10-each-output-root.png) |
| UI-17 | Nền source | Giữ id/amount/tags gốc cùng các field được map. | PASS | [Ảnh](./screenshots/11-base-source.png) |
| UI-18 | Định dạng và undo | Định dạng thành nhiều dòng/thụt Tab; undo trả nguyên chuỗi JSON gọn. | PASS | [Ảnh](./screenshots/24-editor-format-undo.png) |
| UI-19 | Enter/Tab/Shift+Tab | Enter tạo dòng con; Tab tăng và Shift+Tab giảm một cấp thụt. | PASS | Quan sát trực tiếp |
| UI-20 | Mở file JSON lỗi | Hộp lỗi nêu line/column; dữ liệu và preview trước đó được giữ. | PASS | [Ảnh](./screenshots/23-invalid-file-preserves-preview.png) |
| UI-21 | Mở file JSON hợp lệ | Nạp và chuyển đổi thành công với cấu hình each đang có. | PASS | Quan sát trực tiếp |
| UI-22 | Mở composer | Cửa sổ riêng mở với nguồn/rule trống, nút xuất khóa. | PASS | Quan sát trực tiếp |
| UI-23 | Ví dụ ba nguồn | A/B/C được nạp; value/field, wildcard, default, hằng số, rename và delete cho kết quả mong đợi. | PASS | [Ảnh](./screenshots/12-composer-demo.png) |
| UI-24 | Xuất composer | Hai tài liệu JSON bằng nhau hoàn toàn. | PASS | [Ảnh](./screenshots/12-composer-demo.png) |
| UI-25 | Lưu/nạp phiên | Khôi phục A/B/C, mẫu và rule từ dữ liệu nhúng; preview đúng. | PASS | Quan sát trực tiếp |
| UI-26 | Bỏ nguồn đang được tham chiếu | Báo rule 1 chưa nạp nguồn; xuất bị khóa. | PASS | [Ảnh](./screenshots/13-missing-source-error-clipped.png) |
| UI-27 | Bí danh trùng | Từ chối nguồn mới; A và preview hiện có được giữ. | PASS | [Ảnh](./screenshots/14-duplicate-alias-rejected.png) |
| UI-28 | Nạp JSON cấu trúc | Thêm D và dùng làm mẫu; qa_keep=preserved được giữ trong kết quả. | PASS | [Ảnh](./screenshots/15-loaded-template-preserved.png) |
| UI-29 | Sửa mẫu độc lập | Kết quả thay đổi; cây nguồn D vẫn có active/preserved. | PASS | [Ảnh](./screenshots/16-template-independent-from-source.png) |
| UI-30 | Mẫu JSON lỗi | Báo lỗi parse, xóa preview và khóa xuất. | PASS | Quan sát trực tiếp |
| UI-31 | Dùng nguồn làm mẫu | Khôi phục mẫu D và kết quả hợp lệ. | PASS | Quan sát trực tiếp |
| UI-32 | Thu nhánh cây nguồn | Các field con ẩn; các nhánh khác vẫn hiển thị. | PASS | Quan sát trực tiếp |
| UI-33 | Copy value và Copy field | Lần lượt nhận value:D:$.profile và field:D:$.profile, không kèm thụt dòng. | PASS | Quan sát trực tiếp |
| UI-34 | Chặn xung đột path | Báo trùng/chồng path, gợi ý overwrite, giữ preview cũ. | PASS | [Ảnh](./screenshots/19-composer-conflict-rejected.png) |
| UI-35 | Custom rule có prefix | meta.qa_value bằng preserved. | PASS | Quan sát trực tiếp |
| UI-36 | Sửa JSON rule và field làm nguồn | meta.qa_value bằng tên key qa_keep. | PASS | [Ảnh](./screenshots/20-edit-custom-field-reference.png) |
| UI-37 | Overwrite theo thứ tự | Áp dụng được; kết quả là 2. | PASS | [Ảnh](./screenshots/21-overwrite-last-rule-wins.png) |
| UI-38 | Bảo vệ file nguồn | Ứng dụng từ chối; đọc lại fixture xác nhận nội dung còn nguyên. | PASS | [Ảnh](./screenshots/22-source-overwrite-blocked.png) |
| UI-39 | Đóng khi có thay đổi chưa lưu | Cửa sổ đóng không có nhắc lưu. README đã nêu không tự lưu; đây là thiếu cơ chế bảo vệ phiên, không phải vi phạm hành vi đã tài liệu hóa. | UX_GAP | Quan sát trực tiếp |
| UI-40 | Bố cục mặc định/phóng to | Thanh trạng thái/hướng dẫn bị cắt; composer không hiện các combobox Thiếu field/Ghi chồng trong vùng thấy được. | FAIL_UI | [Ảnh](./screenshots/18-composer-rule-options-clipped.png) |
| UI-41 | Nhãn lỗi sau sửa/undo/nạp nguồn | Nhãn đỏ JSON lỗi vẫn còn dù preview đã chạy thành công; format hợp lệ lần nữa mới xóa nhãn. | FAIL_UI | [Ảnh](./screenshots/08-stale-json-error-after-success.png) |
| UI-42 | Khả năng đọc lỗi dài | Thông báo lỗi nằm trên một dòng và bị cắt ngang; phần quan trọng phải cuộn ngang mới đọc được. | UX_GAP | [Ảnh](./screenshots/13-missing-source-error-clipped.png) |
| UI-43 | Path theo ngữ cảnh each | Danh sách vẫn là path từ gốc tài liệu; cần tự chuyển về path tương đối của bản ghi, đúng giới hạn README nhưng dễ dùng sai. | UX_GAP | [Ảnh](./screenshots/10-each-output-root.png) |

**Giới hạn độ phủ cần ghi rõ**

- Ctrl/Shift+click để chọn/xóa nhiều rule: API native không hỗ trợ giữ modifier khi click; test callback/widget hiện có đã đạt. Shift+Down và Ctrl+A không mở rộng lựa chọn trong lần thử.
- Chọn nhiều file trong một hộp Open; đường nạp từng file và phiên nhiều nguồn đã kiểm tra.
- Ctrl+Tab/Ctrl+Shift+Tab, chọn khối nhiều dòng để indent/unindent, mọi tổ hợp phím tắt ở mọi hộp thoại.
- Hiệu năng/hủy tác vụ với file lớn qua UI; dữ liệu thật; nhiều màn hình và các mức DPI khác.
- Toàn bộ biên engine như scalar root, mảng rỗng/lồng sâu, mọi transform lỗi và hardlink/symlink qua màn hình; các ca có trong bộ test hiện hữu được xác minh bằng test bổ trợ.

Bộ test bổ trợ bao phủ nhiều biên engine/CLI, sự bất biến dữ liệu, callback Tk, cấu hình custom, format/undo và kiểm tra ghi đè qua hardlink. Lần cuối chạy trong môi trường desktop với TEMP/TMP nằm trong thư mục QA, kết quả 82 tests OK trong 3.967 giây. Không dùng con số này để khẳng định đã có 82 ca điều khiển màn hình.

**Ưu tiên thực hiện:** sửa bố cục và bảo vệ thay đổi chưa lưu trước; tiếp đến đồng bộ trạng thái lỗi, cách trình bày lỗi và picker path theo ngữ cảnh. Các chức năng lớn như JSON Schema, join theo khóa hoặc streaming nên đi sau khi trải nghiệm hiện tại ổn định.

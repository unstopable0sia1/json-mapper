# JSON Mapper

Tool desktop chuyển cấu trúc **một file JSON sang một file JSON khác** theo bộ
rule tùy chỉnh. Đặt tại `D:\HelloWorld\NCKH2026\json-mapper`.
Python 3.10+ và Tkinter; chỉ dùng thư viện chuẩn. Máy hiện tại đã có Python/Tk.
Dữ liệu được xử lý cục bộ, không gọi API hoặc tải lên dịch vụ khác.

## Mở và sử dụng

Nhấp đúp **`start.cmd`**, hoặc chạy:

```powershell
Set-Location -LiteralPath 'D:\HelloWorld\NCKH2026\json-mapper'
python -X utf8 app.py
```

1. Bấm **Mở JSON nguồn** hoặc dán JSON vào ô bên trái.
2. Bấm **+ Thêm** để thêm rule; nhấp đúp một hàng để sửa. Dùng ↑/↓ để đổi thứ tự.
3. Đặt `Path nguồn`, `Path đích`, phép biến đổi và chính sách khi thiếu field.
4. Bấm **Chuyển đổi (F5)** để xem trước JSON kết quả và báo cáo. Bước này chưa ghi file.
5. Bấm **Xuất JSON…** để chọn file kết quả.
6. Bấm **Lưu rule** để lưu cấu hình; lần sau dùng **Nạp rule** để dùng lại.

Tool mở sẵn ví dụ tổng hợp. Nguồn và rule trong bộ nhớ **không tự lưu khi đóng**;
hãy lưu rule và xuất kết quả cần giữ. Sửa input/rule sẽ xóa preview cũ và khóa
nút xuất cho đến khi chuyển đổi thành công. Tool luôn tính lại trước khi xuất.

Tab **Path nguồn** quét cấu trúc JSON và cho copy path bằng nhấp đúp. Path quét
là path toàn bộ nguồn; khi đặt `Gốc nguồn` hoặc dùng `each`, sửa path rule theo
gốc/bản ghi đã chọn. Tab này quét tối đa 3.000 path/20.000 nút; không cắt dữ liệu
chuyển đổi.

## Mapping cơ bản

Nguồn:

```json
{"a": {"a": "Xin chào"}}
```

Bộ rule:

```json
{
  "version": 1,
  "rules": [
    {"from": "a.a", "to": "b.b"}
  ]
}
```

Kết quả:

```json
{"b": {"b": "Xin chào"}}
```

Rule chạy theo thứ tự. Mặc định output chỉ chứa các field được map; field nguồn
không được map không có trong output. Muốn giữ các field khác, đặt `base: "source"`.
Đây là copy nguồn làm nền rồi thêm/đổi field; field cũ vẫn được giữ, không tự xóa.

## Cú pháp path

| Path | Ý nghĩa |
| --- | --- |
| `a.a` hoặc `$.a.a` | Field `a` trong object `a` |
| `$` | Toàn bộ giá trị gốc đang được map |
| `items[0].name` | Field của phần tử đầu tiên |
| `items[*].name` | Field của từng phần tử mảng |
| `groups[*].items[*].id` | Mảng lồng nhau |
| `["a.b"]` | Key có dấu chấm thật trong tên |
| `["key có khoảng trắng"]` | Key có khoảng trắng/Unicode |
| `[""]` | Key rỗng |

Mapping mảng:

```json
{"from": "orders[*].id", "to": "items[*].code"}
```

Các wildcard `[*]` ở hai phía phải bằng nhau; index nguồn được giữ nguyên và
ghép theo thứ tự. Mảng rỗng được giữ thành mảng rỗng ở đích. Có thể copy **nguyên
mảng** bằng `{"from":"orders","to":"items"}` mà không dùng wildcard.

Chỉ hỗ trợ wildcard mảng; không hỗ trợ recursive descent, filter JSONPath hoặc
wildcard key object. Dùng dấu nháy kép JSON cho literal key. Index không âm, tối
đa 1.000.000. Khoảng trống index đích sẽ thành `null`; ví dụ chỉ ghi `items[2]`
thì hai vị trí đầu là `null`. `skip` trong mảng không nén/gộp các index còn lại.

## Chuyển toàn bộ tài liệu hoặc từng bản ghi

- `mode: "document"` (mặc định): map toàn bộ JSON một lần.
- `mode: "each"`: `source_root` phải trỏ đến mảng; map từng phần tử độc lập,
  tạo mảng kết quả. Bất kỳ bản ghi lỗi sẽ làm cả lượt thất bại, không xuất một
  phần hoặc bỏ âm thầm bản ghi lỗi.
- `source_root` (Gốc nguồn): chọn vùng nguồn trước khi map, mặc định `$`.
- `output_root` (Gốc đích): bọc toàn bộ kết quả vào path đích, mặc định `$`.

Ví dụ file nguồn có `orders: [...]`:

```json
{
  "version": 1,
  "mode": "each",
  "source_root": "orders",
  "output_root": "payload.rows",
  "rules": [
    {"from": "id", "to": "code"},
    {"from": "amount", "to": "total", "transforms": ["integer"]},
    {"value": "VND", "to": "currency"}
  ]
}
```

Kết quả là `{"payload":{"rows":[...]}}`. Trong `each`, path `$`, `id`, v.v.
tham chiếu **phần tử hiện tại**, không phải tài liệu gốc. Không ghép/join mảng
độc lập hoặc lấy dữ liệu bên ngoài tự động. Gốc nguồn/đích không dùng wildcard.

## Hằng số, thiếu field và giá trị null

```json
{"value": "VND", "to": "meta.currency"}
```

`value` nhận mọi giá trị JSON: string, number, boolean, null, object hoặc array.
Trong hộp sửa rule, chọn `value`; chuỗi phải có dấu nháy, ví dụ `"VND"`.

```json
{"from": "user.email", "to": "profile.email", "missing": "default", "default": null}
```

`missing` có thể đặt ở toàn bộ cấu hình và ghi đè theo rule:

- `error`: báo lỗi, không xuất kết quả. Đây là mặc định.
- `skip`: không ghi field đó; báo số lần bỏ qua và path nguồn trong báo cáo.
- `default`: cần giá trị `default` ở rule; chỉ thay field **không tồn tại**.

`null`, `false`, `0`, `""`, `[]` không bị coi là thiếu. Parent là `null` hoặc sai
kiểu sẽ báo lỗi nếu tiếp tục truy cập con. Không đoán số phần tử của mảng bị
thiếu để áp default cho wildcard; có thể default nguyên mảng thành `[]` bằng
rule copy mảng không wildcard. Nếu mọi rule đều skip/tắt, nền trống trả `{}`.

## Phép biến đổi

`transforms` là mảng các bước chạy nối tiếp:

```json
{"from": "age", "to": "person.age", "transforms": ["trim", "integer"]}
```

| Phép biến đổi | Tác dụng / tham số |
| --- | --- |
| `copy` | Giữ nguyên |
| `string` | Đổi sang string; boolean/null thành `"false"`/`"null"` |
| `integer` | Đổi sang số nguyên; từ chối phần thập phân không bằng 0 |
| `number` | Đổi sang số hữu hạn; số thập phân dùng float Python |
| `boolean` | Chỉ nhận bool, 0/1 hoặc chuỗi true/false/0/1 |
| `trim`, `lower`, `upper` | Xử lý string |
| `split` | `{"op":"split","separator":","}`; mặc định dấu phẩy |
| `join` | `{"op":"join","separator":" / "}`; nguồn phải là mảng string |
| `replace` | `{"op":"replace","old":"cũ","new":"mới"}` |
| `lookup` | `{"op":"lookup","values":{"A":"active","I":"inactive"}}` |
| `parse_json` | Parse JSON được chứa trong string |
| `json_string` | Serialize giá trị thành string JSON gọn |

`lookup` có thể thêm `default` cho giá trị không có trong bảng. Với nguồn không
phải string, key lookup là JSON gọn, ví dụ `"false"`, `"null"`, `"1"`.
`integer` giữ chính xác số nguyên lớn; `number` với phần thập phân theo độ chính
xác float thông thường. Không suy kiểu mặc định khi không có transform.

Không chạy Python/JavaScript tùy ý trong rule. Thêm operation mới bằng cách bổ
sung `OPS`, `validate_config()` và `transform()` trong `mapper.py`, kèm test cho
ngữ nghĩa mới. Bảng mapping cũng sửa được chuỗi transforms dạng JSON.

## Cấu hình nâng cao

Nút **Rule JSON nâng cao** sửa toàn bộ cấu hình và đồng bộ trở lại bảng khi áp
dụng. Các field có hỗ trợ:

```json
{
  "version": 1,
  "name": "Cấu hình của tôi",
  "mode": "document",
  "source_root": "$",
  "output_root": "$",
  "base": "empty",
  "template": {"meta": {"version": 2}, "data": {}},
  "missing": "error",
  "on_conflict": "error",
  "rules": [
    {"name": "Tên hiển thị", "enabled": true, "from": "user.name", "to": "data.name"}
  ]
}
```

`template` là giá trị JSON nền được copy riêng cho mỗi bản ghi, **không phải
JSON Schema**. Các field template chưa được map sẽ được giữ. Không kết hợp
template với `base: "source"`. Dùng object/mảng làm container trong template;
parent `null` không tự biến thành object.

`on_conflict: "error"` mặc định từ chối hai rule ghi cùng path hoặc chồng path
cha/con. `overwrite` cho phép chủ đích ghi đè theo thứ tự; vẫn báo lỗi nếu parent
không đúng kiểu container. Template/base có thể được rule ghi lại mà không cần
bật overwrite. Rule `enabled: false` không chạy.

## CLI cho lượt chuyển đổi lặp lại

Chạy từ thư mục tool:

```powershell
python -X utf8 mapper.py examples/input.json examples/mapping.rules.json converted.json --report converted.report.json
python -X utf8 mapper.py examples/input.json examples/each.rules.json each-converted.json
python -X utf8 mapper.py examples/input.json examples/mapping.rules.json --dry-run
```

CLI mặc định yêu cầu file output/report **chưa tồn tại**; dùng tên mới hoặc cờ
`--overwrite` khi chủ đích ghi lại. Cả CLI và GUI từ chối ghi output lên file
nguồn/rule đã nạp, kể cả alias/symlink/hardlink. `--dry-run` chỉ in báo cáo,
không ghi file, kể cả khi có `--report`. Exit 0 là thành công, exit 2 là lỗi.

Báo cáo ghi số bản ghi/giá trị map/default/skip/mảng rỗng; tối đa 1.000 sự kiện
field thiếu đầu tiên. CLI thêm SHA-256 bytes input/rules/output để đối chiếu.
Cùng bytes input/rules và phiên bản code cho cùng bytes output. Khi không dùng
`base: source`, các field nguồn ngoài mapping bị loại; báo cáo không tuyên bố
kiểm kê đầy đủ các field bị loại. Kiểm tra quyền ghi/thư mục trước khi chạy;
lỗi I/O ở lúc ghi report vẫn có thể xảy ra sau khi output đã được ghi.

## Phạm vi và kiểm thử

Đây là tiện ích mapping cấu trúc tổng quát. Ví dụ trong `examples/` là dữ liệu
giả để minh họa/test. Không có dataset nghiên cứu thật được chuyển đổi trong
lần tạo tool này; không có nguồn A/B nghiên cứu, target/cutoff, split, annotation
hoặc training-use mới được phê duyệt. Khi áp dụng vào dataset thật, cần chốt
contract và ý nghĩa từng mapping theo quy trình của project tương ứng.

Tool parse/kiểm rule và kiểu container/transform; **không tự chứng nhận tương
đương ngữ nghĩa hay validate một JSON Schema đích**. Không tự tạo nhãn, eligibility
hoặc đổi model. Hỗ trợ JSON UTF-8 (có/không BOM), object/array/scalar ở gốc;
từ chối duplicate keys và NaN/Infinity. Đọc toàn bộ vào RAM, không hỗ trợ JSONL
hoặc streaming file rất lớn.

Chạy kiểm thử engine, CLI và widget/callback Tk:

```powershell
python -X utf8 -m unittest discover -s tests -v
```

Windows có Tk cần dùng để chạy GUI tests; test engine/CLI riêng có thể chạy bằng
`python -X utf8 -m unittest discover -s tests -p test_mapper.py -v`.

Ngày tạo: 29/10/2026 (Asia/Saigon). Tool nằm ngoài các repository nghiên cứu;
chỉ tạo code, cấu hình ví dụ và tests trong chính thư mục này.

Kiểm chứng 29/10/2026: **43 tests PASS** bằng lệnh trên, gồm engine, CLI và
widget/callback Tk (nạp/lưu rule, sửa input, preview, export). Có ca 10.000 phần
tử mảng/20.000 giá trị map, bảo toàn nguồn, chặn ghi chồng qua hardlink và
round-trip GUI → file. GUI tests dùng dialog giả cho chọn file; chưa có kiểm
thao tác thủ công/visual QA. `py -3` có Tk 8.6; CLI ví dụ `each --dry-run` đạt.

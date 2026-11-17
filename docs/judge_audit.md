# Judge audit

Chạy trong `src/`:
- `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5`
- `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Tỉ lệ fail quan sát → hiệu chỉnh (Rogan-Gladen) | Ma trận nhầm lẫn (`FAIL` = positive) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | 0.280 → 0.300 | `tp=24, fp=4, fn=6, tn=66` | **Đạt** (`0.757≥0.6`, `0.857≥0.8`, `0.800≥0.7`) | **dùng** (cho tiêu chí giọng điệu, kèm audit định kỳ) |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | 0.090 → 0.300 | `tp=9, fp=0, fn=21, tn=70` | **Không đạt** (`κ=0.375 < 0.6`, `R=0.300 < 0.7`) | **loại** khỏi release gate |

## Audit thủ công toàn bộ 10 bất đồng của `tone_ok` và 3 ca đại diện của `helpful` (13 ca ≥ 5 ca yêu cầu)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & hướng sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`): `"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."` | `PASS` | `FAIL` | Người đúng (`FN`) | Xưng `"em"` + `"nha"` quá suồng sã; sửa rubric `tone_ok`: bắt buộc xưng `"LogiX"` với khách `"anh/chị"`, cấm tự xưng `"em"` hay trợ từ thân mật (`nha`, `nhé`). |
| 2 | `H-017` (`tone_ok`): `"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."` | `PASS` | `FAIL` | Người đúng (`FN`) | Gọi khách là `"bạn ơi"` kèm `"rồi nha"` dù có `"Dạ"`; cập nhật rubric: bất kỳ đại từ `"bạn"` hướng về khách đều `FAIL`. |
| 3 | `H-029` (`tone_ok`): `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` | `PASS` | `FAIL` | Người đúng (`FN`) | Đầu câu có `"Dạ, vui lòng"` nhưng cuối câu ra lệnh `"không cần nhắn thêm"`; sửa rubric: đánh giá toàn câu, cấm ngữ điệu đuổi/ra lệnh khách. |
| 4 | `H-042` (`tone_ok`): `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` | `FAIL` | `PASS` | Người đúng (`FP`) | Judge phạt nhầm vì thiếu câu xin lỗi dù đây là ca thông báo hoàn tiền ngắn gọn, đủ ý và lịch sự; sửa rubric: không bắt buộc xin lỗi khi câu trả lời xác nhận kết quả tích cực. |
| 5 | `H-051` (`tone_ok`): `"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."` | `FAIL` | `PASS` | Người đúng (`FP`) | Judge phạt nhầm vì có từ tiếng Anh `"refund"`; sửa rubric: cho phép danh sách thuật ngữ CS chuẩn (`refund`, `LogiX`) nếu cấu trúc câu vẫn lịch sự bằng tiếng Việt. |
| 6 | `H-063` (`tone_ok`): `"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."` | `PASS` | `FAIL` | Người đúng (`FN`) | Hứa `"sẽ hoàn thêm"` ngoài kết quả hệ thống; bổ sung rubric: đánh `FAIL` mọi câu hứa hẹn bồi thường bổ sung không có trong kết quả. |
| 7 | `H-070` (`tone_ok`): `"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"` | `PASS` | `FAIL` | Người đúng (`FN`) | Emoji cười khóc (`😂😂`) không phù hợp ngữ cảnh khiếu nại; thêm rule vào rubric: cấm emoji cợt nhả/không trang trọng trong phản hồi CS. |
| 8 | `H-081` (`tone_ok`): `"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."` | `FAIL` | `PASS` | **Judge đúng** (sửa nhãn người) | Người gán nhãn đọc nhầm ticket (`note`: *"nhãn người sai (đọc nhầm ticket) — judge đúng, sửa nhãn"*); sửa nhãn vàng `H-081` thành `FAIL` và quy định kiểm chéo 2 người với ca biên. |
| 9 | `H-088` (`tone_ok`): `"Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ."` | `FAIL` | `PASS` | Người đúng (`FP`) | Lặp `"Dạ, dạ,"` do lỗi gõ nhỏ nhưng vẫn lịch sự; làm rõ rubric: lỗi gõ lặp từ nhỏ không làm sai chuẩn lịch sự không bị phạt `FAIL`. |
| 10 | `H-094` (`tone_ok`): `"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."` | `PASS` | `FAIL` | Người đúng (`FN`) | Tiếng Việt không dấu kiểu dịch máy thiếu chuyên nghiệp; bổ sung rubric: câu phản hồi tiếng Việt mất dấu hàng loạt phải đánh `FAIL`. |
| 11 | `HL-015` (`helpful`): `"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."` | `PASS` | `FAIL` | Người đúng (`FN`) | Ledger chỉ ghi `40.000đ` nhưng reply báo `55.000đ` (`FM-08`); judge chỉ đọc text nên không thể đối chiếu ledger. Không dùng judge chấm tiền — tách sang code grader ở M3. |
| 12 | `HL-016` (`helpful`): `"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này... LogiX đã hoàn 55.000đ cho đơn O-404..."` | `PASS` | `FAIL` | Người đúng (`FN`) | Ledger chỉ ghi `35.000đ`; câu xin lỗi dài, lặp lại 2 lần tạo hiệu ứng *verbosity/politeness bias* khiến judge chấm `PASS`. |
| 13 | `HL-047` (`helpful`): `"Ok bạn, đơn O-515 xử lý rồi nhé."` | `PASS` | `FAIL` | Người đúng (`FN`) | Xưng `"Ok bạn"` sai chuẩn và không nêu số tiền/trạng thái cụ thể; sửa rubric `helpful`: bắt buộc nêu rõ kết quả xử lý (đã hoàn bao nhiêu / lý do từ chối) và giữ chuẩn xưng hô trước khi chấm đạt. |

## Kết luận
- **Tiêu chí bị loại và lý do:** Loại **`helpful`** (`judge_helpful_public.csv`) khỏi release gate. Dù `precision = 1.000` (`fp = 0`), judge bị **`fn = 21`** (`recall = 0.300 < 0.700`, `κ = 0.375 < 0.600`), khiến tỉ lệ fail quan sát bị kéo xuống **`0.090`** trong khi tỉ lệ fail thực sau hiệu chỉnh Rogan-Gladen là **`0.300`** (bỏ lọt `70%` tổng số fail). Phân rã theo `human_failure` trên `n=100`: `helpful` chỉ bắt được `9` ca lỗi bề mặt (`giọng cụt`: 4, `không hỏi lại mã đơn`: 3, `trả lời lạc đề`: 2), nhưng **bỏ lọt 100% hai nhóm lỗi sau**: `18/18` ca **sai tiền (`FM-08`)** — gồm `5` ca ngắn gọn (`HL-015, HL-020, HL-062, HL-087, HL-100`) do judge không truy cập `refund_ledger` và `13` ca xin lỗi lặp dài (*verbosity/politeness bias*, vd. `HL-016`) — cộng `3/3` ca `sai xưng hô` (`HL-047, HL-091, HL-097`).
- **Cách khắc phục:** Chỉ dùng `tone_ok` (đã đạt FLOORS `κ=0.757, P=0.857, R=0.800`) cho tiêu chí giọng điệu, kết hợp cập nhật rubric theo 10 ca đã audit (`H-008/017` cấm `em`/`bạn`/`nha`, `H-029` cấm câu ra lệnh, `H-063` cấm `"sẽ hoàn thêm"`, `H-070` cấm emoji, `H-094` cấm mất dấu, `H-042/051/088` không phạt oan câu ngắn/từ `"refund"`/lỗi lặp `"Dạ"`) và sửa nhãn `H-081`; còn phần đúng/sai số tiền (`FM-08`) bắt buộc giao cho **code grader** đối chiếu `refund_ledger` ở **M3**.
- **Rủi ro còn lại & chống overfit rubric:** Các ca trên thuộc tập `*_public.csv` (`n=100`) — sau khi sửa rubric cho `tone_ok`, không được dùng chính tập này để khẳng định calibration mới mà phải kiểm lại trên tập *held-out* do người gán nhãn độc lập, đồng thời audit định kỳ khi thay prompt hoặc model mới.

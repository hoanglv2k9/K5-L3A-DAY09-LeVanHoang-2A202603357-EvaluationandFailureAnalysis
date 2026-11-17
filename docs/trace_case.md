# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (`run_id`: `R-seeded_regression-C-002-s11`) |
| Triệu chứng | Grader Lab 8 (`trial_pass`) FAIL với lý do `status resolved != denied`. Ledger ghi `refund_vnd = 20000`, `refund_count = 1`, event 6 `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`, trong khi nhãn đúng của `C-002` là `denied`, `refund_vnd = 0`, `refund_count = 0`. |
| Bước sai đầu tiên | Event `3` (`kind: model_override`): `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `1` (`handoff`) giữ đúng allowlist `principal_scope: owner_order_only`, `facts: {}` và chỉ cấp tool đọc; Event `2` (`investigator`) gọi `lookup_order` trả đúng dữ liệu DB (`order_id: O-202`, `status: delivered`, `delay_days: 2`, `shipping_fee_vnd: 20000`). Tới Event `3`, agent lấy số `"trễ 5 ngày"` từ ticket ghi đè `delay_days = 2` của DB, gây ra sai dây chuyền ở Event `4` (`quote` = `20000`) và chi sai vào ledger. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11` (`R-fixed-C-002-s11`): không có event `model_override`. Sau Event `2` (`lookup_order` với `delay_days: 2`), Event `3` (`quote`) trả `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`, Event `4` (`reply`) báo không đủ điều kiện, ledger `0`, status `denied` (PASS). |
| Regression test | `tests/test_lab9_regression.py::test_fm03_c002_trace_regression` (kiểm `DbFactKept().evaluate(...)` và `trial_pass`: FAIL trên `seeded_regression C-002@11` do có event `model_override`, PASS trên `fixed C-002@11`). |
| Chưa chắc chắn | Trace chạy trên `MockLLM` với regex `parse_delay_days`, chưa đo các cách diễn đạt mơ hồ tự nhiên của LLM thật; đồng thời cùng lỗi `ticket_trust` trên `C-002` nếu variant không ghi event `model_override` (`quiet_override` ở M5–M7) thì grader `DbFactKept` một mình chưa bắt được mà phải dựa vào `TrialPass` / `RefundAmountCorrect`. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

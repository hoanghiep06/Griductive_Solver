# Interaction Effects

Các hiệu ứng trong cụm tương tác chỉ thay đổi presentation/orchestration. SAT,
CNF, DPLL và điều kiện chấp nhận verdict trong `GameEngine` không thay đổi.

- **Load Puzzle:** mở kho hồ sơ hiện có; khi chuyển trang, `ScreenRouter` fade
  màn mới trong 260 ms. Ván hiện tại chỉ bị thay sau khi puzzle mới nạp thành
  công.
- **Restart:** từ hai bước đã xác nhận trở lên, UI mở modal “Tái dựng hồ sơ”.
  Sau xác nhận, bộ thẻ cũ co và biến mất theo nhịp so le; bộ thẻ ban đầu được
  chia lại với hiệu ứng settle. Esc hoặc nút giữ hồ sơ sẽ hủy modal.
- **Hint:** manh mối và ô hỗ trợ phát các hạt sáng chạy theo đường cong tới ô
  kết luận. Khung giải thích trình bày chuỗi Chứng cứ → Thử giả thiết ngược →
  Mâu thuẫn → Kết luận trước khi thẻ được lật.
- **Auto Solve:** thanh Nhịp tự giải điều chỉnh được từ 250 đến 1200 ms/bước,
  kể cả khi đang chạy. Pause vẫn hủy kết quả chờ theo generation/KB version.
- **Logic feedback:** NOT_PROVABLE dùng modal amber; CONTRADICTED dùng modal
  rose và nút Soi điểm mâu thuẫn. Banner gọn vẫn được giữ để người chơi không
  mất ngữ cảnh sau khi đóng modal.

Mọi duration mới nằm trong `src/gui/animations/motion_config.py`. Reduced
Motion bỏ particle/rebuild animation nhưng giữ nguyên nội dung và hành vi.

Kiểm thử chính:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests/gui/test_interaction_upgrade.py `
  tests/gui/test_phase4_dashboard_and_screens.py `
  tests/gui/test_phase5_motion_and_integration.py -q
```

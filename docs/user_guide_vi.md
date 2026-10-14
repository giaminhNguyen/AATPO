# Hướng dẫn sử dụng AATPO (Văn phòng AI)

AATPO là phần mềm chạy trên máy Windows của bạn. Bạn mô tả việc bằng tiếng Việt; AATPO nhờ các trợ lý AI **đã cài và đã đăng nhập sẵn trên máy bạn** (Claude Code, Codex) làm việc, tự kiểm tra, lưu lịch sử phiên bản và báo cáo lại. Bạn **không cần gõ lệnh** hay biết lập trình.

## 1. Trước khi dùng (làm một lần)
- Cài **Git for Windows** (để có lịch sử phiên bản). Không cần tài khoản GitHub.
- Cài và đăng nhập **ít nhất một** trợ lý: Claude Code hoặc Codex. Mục **Cài đặt** cho biết trợ lý nào đã “Sẵn sàng”.
- Hãy **sao lưu** thư mục dự án quan trọng trước khi giao việc. Lịch sử phiên bản chỉ nằm trên máy này, không phải bản sao lưu.
- Không chạy AATPO bằng quyền Administrator. Chỉ dùng với dự án bạn tin tưởng.

## 2. Chọn dự án (mục **Dự án**)
1. **Mở dự án có sẵn…** hoặc **Tạo dự án mới…** → chọn thư mục → kiểm tra tên và đường dẫn → **Xác nhận**.
2. Nếu thư mục chưa có lịch sử phiên bản, tích chọn **“Tự động lưu lịch sử phiên bản (khuyên dùng)”**. Nếu đã có sẵn, AATPO giữ nguyên, không đổi nhánh hay xóa gì của bạn.
3. **Lệnh kiểm thử…**: xác nhận lệnh để AATPO tự chạy thử sau khi sửa (ví dụ `python -m pytest -q`). Có lệnh này, kết quả được kiểm chứng bằng chạy thử thật; không có thì báo cáo sẽ ghi rõ “chưa chạy thử”.
4. **Tên người lưu phiên bản…**: chỉ cần khi máy chưa có tên/email cho lịch sử phiên bản. AATPO không tự bịa tên bạn.
5. Nếu thư mục bị di chuyển, dự án hiện “Không tìm thấy thư mục dự án” → **Liên kết lại thư mục…**.

## 3. Giao việc (mục **Văn phòng AI**)
Gõ tiếng Việt tự nhiên, ví dụ:
- *“Tôi cần làm ứng dụng quản lý kho đơn giản”*
- *“Sửa lỗi đăng nhập”*, *“Sửa lại nút lưu”*
- *“Cho tôi xem đã làm gì”*, *“Dừng việc này”*, *“Bắt đầu làm”*

Trợ lý hỏi **một** câu mỗi lần. Chưa biết trả lời gì thì bấm **“Tôi chưa biết, hãy đề xuất”**.
Nhắn “đồng ý” trong ô trò chuyện **không có hiệu lực**: bạn phải bấm nút ở mục quyết định.

## 4. Quyết định (mục **Cần bạn quyết định**)
AATPO đưa hai phương án: **Tiết kiệm** (ít việc nhất, ít chi phí) và **Cân bằng**; liệt kê rõ mục *Bắt buộc / Nên có / Để sau / Không làm* và quy mô (XS nhỏ … XL lớn). Bấm **Đồng ý — …** hoặc **Không đồng ý**. Chưa duyệt thì AATPO **không** bắt đầu làm. Mục này cũng hỏi bạn khi một việc bị gián đoạn đột ngột và cần chạy lại.

## 5. Theo dõi (mục **Công việc**)
- **Bắt đầu**, **Tạm dừng**, **Tiếp tục**, **Xem chi tiết**, **Xem kết quả**.
- Trạng thái dùng chữ thường: *Đang thực hiện, Đang kiểm tra, Cần làm lại, Bị chặn, Hoàn thành…* Thanh “n/m việc xong” chỉ đếm việc đã có bằng chứng.
- Thấy “Đang có tiến trình thật chạy ngầm” nghĩa là một trợ lý đang thực sự chạy.
- **Bị chặn** vì “thay đổi chưa lưu”: bạn lưu hoặc hoàn tác thay đổi của mình, rồi bấm **Tiếp tục**. AATPO không tự cất hay xóa thay đổi của bạn.
- **Tích hợp vào nhánh chính**: khi kết quả đã sẵn sàng nhưng chưa được gộp vào nhánh chính, bấm nút này để gộp (gộp thẳng, không ghi đè).

## 6. Kết quả (mục **Kết quả**)
Báo cáo gồm: yêu cầu, phạm vi đã duyệt, từng việc và kết quả kiểm tra, kết quả chạy thử, phiên bản đã lưu, tình trạng tích hợp, **điều chưa làm và rủi ro**.
Nút: **Mở thư mục dự án**, **Xem thay đổi**, **Lưu báo cáo…**, **Sao chép báo cáo**, **Yêu cầu chỉnh sửa**, **Chấp nhận kết quả**. AATPO **không tự chạy** sản phẩm vừa làm.

## 7. Điều AATPO không làm
Không đẩy mã lên mạng (không push), không xóa hay viết lại lịch sử, không triển khai lên môi trường thật, không tự chi tiền, không đọc hay sao chép thông tin đăng nhập của trợ lý AI.

## 8. Quyền riêng tư
Khi trợ lý AI làm việc, nội dung dự án và tin nhắn liên quan được gửi tới dịch vụ của nhà cung cấp (Claude/OpenAI) theo quy định của họ và có thể tính vào hạn mức của bạn. Mọi lần gửi dữ liệu đều hỏi bạn trước (ví dụ nút thử ở **Cài đặt**, công tắc “Dùng trợ lý AI để hiểu câu lệnh phức tạp”).

## 9. Khi gặp sự cố
- “Chưa cài / Chưa đăng nhập / Hết hạn mức” ở **Cài đặt**: làm theo trạng thái, rồi **Kiểm tra lại**.
- Mất điện/đóng đột ngột lúc đang chạy: việc đó hiện **Cần bạn xem lại** và hỏi bạn có cho chạy lại không; AATPO không tự chạy lại.
- Chi tiết kỹ thuật (mã phiên, mã thoát) nằm trong mục **Chi tiết kỹ thuật** thu gọn ở **Cài đặt**.

## 10. Giới hạn trung thực
AATPO không cô lập hệ điều hành: trợ lý chạy với quyền tài khoản Windows của bạn; các quy tắc đường dẫn và kiểm tra chỉ là lớp bảo vệ, không phải “hộp cát”. Bước kiểm tra bằng AI không độc lập hoàn toàn, nên hãy tự thử các chức năng quan trọng.

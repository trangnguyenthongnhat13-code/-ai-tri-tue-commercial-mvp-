# AI Trí Tuệ — Commercial MVP

MVP này biến một yêu cầu tự nhiên thành đầu ra dùng được: nghiên cứu/nội dung, audio MP3, video MP4 dọc 9:16, hoặc landing page HTML.

## Luồng chính
1. Người dùng nói nhu cầu bằng tiếng Việt.
2. AI tự viết nội dung/kịch bản phù hợp.
3. Với audio: tạo MP3 bằng OpenAI TTS.
4. Với video: tạo 3 ảnh minh hoạ nếu người dùng không tải ảnh, tạo voice, subtitle, rồi render MP4 bằng FFmpeg.
5. Với landing page: thực hiện preflight; nếu thiếu dữ liệu thương mại bắt buộc thì trả về danh sách cần bổ sung. Nếu người dùng nói "bổ sung sau" cho phần tùy chọn, AI vẫn dựng trang.

## Cài đặt
- Python 3.11+
- FFmpeg có trong PATH
- OpenAI API key

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# điền OPENAI_API_KEY vào .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Mở http://localhost:8000

## Lưu ý thương mại
- API key chỉ nằm ở server, tuyệt đối không đưa xuống trình duyệt khách hàng.
- Video chuẩn MVP là 3 ảnh + chuyển động nhẹ + voice + subtitle, nhằm kiểm soát giá vốn.
- Không tự bịa giá, số điện thoại, địa chỉ, review, chính sách hoặc cam kết sức khỏe/tài chính.
- Đây là bản MVP để Trang dùng thật trước. Trước khi bán đại trà cần thêm đăng nhập, thanh toán, quota, lưu trữ cloud, dashboard quản trị và logging chi phí.

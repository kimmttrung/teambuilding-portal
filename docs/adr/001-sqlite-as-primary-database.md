# ADR-001 – Dùng SQLite làm cơ sở dữ liệu chính

**Trạng thái**: Accepted · **Ngày**: 10/09/2026

## Bối cảnh
Mentor yêu cầu SQLite. Hệ thống phục vụ ≤1.000 CBNV/kỳ, có một khoảnh khắc tải cao duy nhất:
lúc mở chọn ghế Gala Dinner (nhiều team thao tác đồng thời).

## Quyết định
Dùng SQLite ở chế độ WAL làm CSDL chính, quản lý schema bằng Alembic.

## Hệ quả
**Được**: không cần service DB riêng, backup = copy 1 file, demo cực nhanh, `docker compose up` là chạy.

**Mất / phải xử lý**:
- SQLite chỉ cho **một writer tại một thời điểm** → mọi transaction ghi phải ngắn; thao tác tranh chấp dùng `BEGIN IMMEDIATE`; đặt `busy_timeout=5000`.
- Foreign key **mặc định tắt** → phải `PRAGMA foreign_keys=ON` ở mỗi connection, kèm test xác nhận.
- Không có kiểu `ENUM`, `JSONB`, `ALTER COLUMN` đầy đủ → dùng `TEXT` + `CHECK`, và Alembic batch mode khi đổi cột.
- Không nhiều instance backend cùng ghi một file qua mạng.

## Khi nào phải chuyển sang PostgreSQL
Nếu vượt bất kỳ ngưỡng nào: >1.000 người dùng đồng thời, cần chạy nhiều instance backend,
hoặc cần replica đọc. Vì đã dùng SQLAlchemy + Alembic, chi phí chuyển đổi chủ yếu là kiểu dữ liệu và PRAGMA.

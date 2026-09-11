"""Tạo tài khoản từ dòng lệnh.

Cần thiết vì database mới toanh chưa có ai để đăng nhập. Dùng để tạo admin đầu tiên;
dữ liệu mẫu đầy đủ thì dùng scripts/seed.py.

    python scripts/create_user.py --email btc@company.vn --role admin
    python scripts/create_user.py --email a@company.vn --password MatKhau123 --name "Nguyễn Văn A"
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import session_scope  # noqa: E402
from app.core.security import generate_password, hash_password  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import get_user_by_email  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo tài khoản người dùng")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="Bỏ trống để hệ thống tự sinh")
    parser.add_argument("--name", default=None, help="Họ tên đầy đủ")
    parser.add_argument(
        "--role",
        default=UserRole.EMPLOYEE,
        choices=[role.value for role in UserRole],
    )
    parser.add_argument("--employee-code", default=None)
    parser.add_argument(
        "--reset", action="store_true", help="Nếu email đã tồn tại thì đặt lại mật khẩu"
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = args.password or generate_password()

    with session_scope() as db:
        existing = get_user_by_email(db, email)
        if existing and not args.reset:
            print(f"Tài khoản {email} đã tồn tại. Thêm --reset để đặt lại mật khẩu.")
            return 1

        if existing:
            existing.password_hash = hash_password(password)
            existing.must_change_password = True
            existing.failed_login_count = 0
            existing.locked_until = None
            action = "Đã đặt lại mật khẩu"
        else:
            db.add(
                User(
                    email=email,
                    full_name=args.name or email.split("@")[0],
                    employee_code=args.employee_code,
                    password_hash=hash_password(password),
                    role=args.role,
                    must_change_password=not args.password,
                )
            )
            action = "Đã tạo tài khoản"

    print(f"{action}: {email}")
    print(f"  Vai trò:   {args.role}")
    print(f"  Mật khẩu:  {password}")
    if not args.password:
        print("  (mật khẩu tự sinh — người dùng phải đổi ở lần đăng nhập đầu)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

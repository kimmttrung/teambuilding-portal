"""SMTP server giả cho môi trường dev: nhận thư, in ra màn hình, lưu ra file.

Dùng khi muốn xem email thật sự hiển thị thế nào mà không cần Gmail, không cần Docker,
không cần tài khoản nào. Nhận xong, mỗi thư được lưu 2 file trong `data/dev_mail/`:
`.eml` (mở bằng Outlook/Thunderbird) và `.html` (mở bằng trình duyệt).

    # Cửa sổ terminal 1
    py -3.13 scripts/dev_smtp_server.py

    # .env
    EMAIL_ENABLED=true
    SMTP_HOST=127.0.0.1
    SMTP_PORT=1025
    SMTP_STARTTLS=false        # server này không nói TLS
    SMTP_USER=
    SMTP_PASSWORD=

    # Cửa sổ terminal 2
    py -3.13 scripts/send_test_email.py --to ai-cung-duoc@example.com

Chỉ dùng để dev. Server chấp nhận mọi lệnh AUTH và không gửi thư đi đâu cả —
đó chính là điểm mạnh: không bao giờ có nguy cơ gửi thư thật cho 122 CBNV lúc đang thử.
"""

import argparse
import asyncio
import re
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
MAIL_DIR = BACKEND_DIR / "data" / "dev_mail"


class SmtpSession:
    """Một phiên SMTP. Chỉ đỡ đủ lệnh để smtplib làm việc được."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.recipients: list[str] = []

    async def run(self) -> None:
        self._send(b"220 dev-smtp san sang")
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    return
                if not await self._handle(line.rstrip(b"\r\n")):
                    return
        finally:
            self.writer.close()

    async def _handle(self, line: bytes) -> bool:
        command = line.upper()

        if command.startswith((b"EHLO", b"HELO")):
            # Cố tình KHÔNG quảng cáo STARTTLS: server này không có TLS, nói có là
            # smtplib sẽ thử nâng cấp rồi lỗi giữa đường.
            self._send(b"250-dev-smtp\r\n250-AUTH PLAIN LOGIN\r\n250 OK")
        elif command.startswith(b"AUTH"):
            self._send(b"235 2.7.0 chap nhan moi thu (dev)")
        elif command.startswith(b"MAIL"):
            self._send(b"250 OK")
        elif command.startswith(b"RCPT"):
            match = re.search(rb"<([^>]*)>", line)
            self.recipients.append((match.group(1) if match else b"?").decode())
            self._send(b"250 OK")
        elif command.startswith(b"DATA"):
            self._send(b"354 Gui noi dung, ket thuc bang <CRLF>.<CRLF>")
            await self._read_message()
        elif command.startswith(b"RSET"):
            self.recipients.clear()
            self._send(b"250 OK")
        elif command.startswith(b"NOOP"):
            self._send(b"250 OK")
        elif command.startswith(b"QUIT"):
            self._send(b"221 Tam biet")
            return False
        else:
            self._send(b"250 OK")
        return True

    async def _read_message(self) -> None:
        lines: list[bytes] = []
        while True:
            line = await self.reader.readline()
            if not line or line.rstrip(b"\r\n") == b".":
                break
            # Bỏ dấu chấm nhân đôi ở đầu dòng (quy tắc dot-stuffing của SMTP).
            if line.startswith(b".."):
                line = line[1:]
            lines.append(line.replace(b"\r\n", b"\n"))

        save_message(b"".join(lines), self.recipients)
        self.recipients.clear()
        self._send(b"250 OK da nhan")

    def _send(self, payload: bytes) -> None:
        self.writer.write(payload + b"\r\n")


def save_message(raw: bytes, recipients: list[str]) -> None:
    message = message_from_bytes(raw)
    subject = str(make_header(decode_header(message.get("Subject", "(khong co tieu de)"))))
    stamp = datetime.now().strftime("%H%M%S")

    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    base = MAIL_DIR / f"{datetime.now():%Y%m%d}_{stamp}_{_slug(subject)}"
    (base.with_suffix(".eml")).write_bytes(raw)

    html = _part(message, "html")
    if html:
        base.with_suffix(".html").write_text(html, encoding="utf-8")

    print("=" * 70)
    print(f"Tới      : {', '.join(recipients) or message.get('To', '?')}")
    print(f"Từ       : {message.get('From', '?')}")
    print(f"Tiêu đề  : {subject}")
    print(f"File     : {base.with_suffix('.eml').relative_to(BACKEND_DIR)}")
    if html:
        print(f"           {base.with_suffix('.html').relative_to(BACKEND_DIR)}  <- mở bằng trình duyệt")
    text = _part(message, "plain")
    if text:
        print("-" * 70)
        print(text.strip())
    print("=" * 70, flush=True)


def _part(message, subtype: str) -> str | None:
    for part in message.walk():
        if part.get_content_type() == f"text/{subtype}":
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            return payload.decode(part.get_content_charset() or "utf-8", "replace")
    return None


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip()
    return re.sub(r"[\s]+", "-", cleaned)[:50] or "email"


async def serve(host: str, port: int) -> None:
    async def handle(reader, writer):
        await SmtpSession(reader, writer).run()

    server = await asyncio.start_server(handle, host, port)
    print(f"dev-smtp: đang nghe {host}:{port} — Ctrl+C để dừng")
    print(f"Thư nhận được lưu tại: {MAIL_DIR}")
    async with server:
        await server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="SMTP server giả cho dev")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()

    try:
        asyncio.run(serve(args.host, args.port))
    except KeyboardInterrupt:
        print("\ndev-smtp: đã dừng")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

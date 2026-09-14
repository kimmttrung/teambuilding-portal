# Backend Team Building Portal — FastAPI + SQLite (docs/08-devops.md §5).
# Cùng minor version với máy dev (3.13) để không có lỗi "chạy được trên máy tôi".
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cài thư viện TRƯỚC khi copy code: sửa code không phải cài lại (tận dụng cache layer).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Chạy bằng user thường. Thư mục data thuộc user này sẵn trong image, nên named volume tạo lần đầu
# kế thừa đúng quyền — không cần chown lúc khởi động.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --no-create-home app

COPY --chown=app:app . .
RUN sed -i 's/\r$//' docker/entrypoint.sh \
    && chmod +x docker/entrypoint.sh \
    && mkdir -p data/sqlite data/uploads data/chromadb data/backups \
    && chown -R app:app data

USER app
EXPOSE 8000

# /health luôn trả HTTP 200 — phải đọc `status`: DB không mở được hoặc foreign_keys tắt là "degraded".
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import json,sys,urllib.request; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)); sys.exit(0 if r.get('status') == 'ok' else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["serve"]

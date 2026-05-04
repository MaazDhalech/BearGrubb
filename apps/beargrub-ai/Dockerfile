FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BEARGRUB_AUTO_INIT=1 \
    BEARGRUB_TEST_MODE=0 \
    CHAINLIT_HOST=0.0.0.0 \
    CHAINLIT_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', os.getenv('CHAINLIT_PORT', '8000')); urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=3).read(1)"

CMD ["sh", "-c", "chainlit run app.py --host 0.0.0.0 --port ${PORT:-8000}"]

FROM python:3.12.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --default-timeout=120 --retries=5 -r requirements.txt \
    && python -c "from temporalio.client import Client; from temporalio.worker import Worker"
COPY hello/ hello/
USER 1000:1000
CMD ["python", "-m", "hello.worker"]

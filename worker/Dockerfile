FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --default-timeout=120 --retries=5 -r requirements.txt \
    && python -c "from temporalio.client import Client; from temporalio.worker import Worker"
ARG QC_CODE_VERSION=development
ENV QC_CODE_VERSION=$QC_CODE_VERSION
COPY pool-requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --no-deps -r pool-requirements.txt
COPY qc/ qc/
COPY config/ config/
COPY sql/ sql/
COPY hello/ hello/
ARG TARGETARCH
ADD https://github.com/foxglove/mcap/releases/download/releases/mcap-cli/v0.3.0/mcap-linux-$TARGETARCH /usr/local/bin/mcap
RUN case "$TARGETARCH" in \
      amd64) checksum=5d4100573fab880f1c6400952466275bb3b32c3d230a54f7c380ee0d08e59eef ;; \
      arm64) checksum=be9734ef63ada9d0cc7a3aa41378ab65fd482601e5f5b3b52098d8e6553deabf ;; \
      *) exit 1 ;; esac \
    && echo "$checksum  /usr/local/bin/mcap" | sha256sum -c - \
    && chmod +x /usr/local/bin/mcap
USER 1000:1000
CMD ["python", "-m", "hello.worker"]

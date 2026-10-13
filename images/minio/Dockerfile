# Official MinIO source: RELEASE.2025-10-15T17-29-55Z.
FROM golang:1.24.9-bookworm@sha256:737b40b61ce956d738bed59f18ba854d8d67e7a4c4fa63f64437f4c70247ac5b AS build
ENV CGO_ENABLED=0 GOMAXPROCS=2 GOMEMLIMIT=1GiB GOFLAGS=-p=2
WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git . \
    && test "$(git rev-parse HEAD)" = 9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
RUN go build -trimpath -ldflags="-s -w -X github.com/minio/minio/cmd.Version=2025-10-15T17:29:55Z -X github.com/minio/minio/cmd.ReleaseTag=RELEASE.2025-10-15T17-29-55Z -X github.com/minio/minio/cmd.CommitID=9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" -o /out/minio .

FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /out/minio /usr/local/bin/minio
USER 1000:1000
EXPOSE 9000 9001
ENTRYPOINT ["minio"]

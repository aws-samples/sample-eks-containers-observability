FROM --platform=linux/arm64 public.ecr.aws/docker/library/golang:1.23-bookworm AS builder

WORKDIR /app
COPY go.mod go.sum ./
COPY vendor ./vendor

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -mod=vendor -o main .

FROM --platform=linux/amd64 public.ecr.aws/docker/library/alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/

COPY --from=builder /app/main .

EXPOSE 8080

CMD ["./main"]
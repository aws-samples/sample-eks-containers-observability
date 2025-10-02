FROM public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y gcc python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc python3-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY app.py .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
ENV OTEL_METRICS_EXPORTER=otlp
ENV OTEL_LOGS_EXPORTER=otlp
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_PROPAGATORS=xray,tracecontext,baggage

CMD ["python", "app.py"]

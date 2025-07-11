FROM public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Expose port for Prometheus metrics
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]

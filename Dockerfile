FROM python:3.11-slim

WORKDIR /app

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY backend ./backend
COPY frontend ./frontend
COPY run.py .

# Education (LLM + web) mode; bind to all interfaces for the cloud platform.
ENV ASSISTANT_MODE=education \
    HOST=0.0.0.0 \
    PORT=8001 \
    PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["python", "run.py"]

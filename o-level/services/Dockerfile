FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
ENV PYTHONUNBUFFERED=1
# Which service to run is picked by the compose file: frontend.py or inventory.py

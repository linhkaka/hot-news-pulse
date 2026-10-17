FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./

# config.json, .env and the database live in the mounted /data folder.
ENV DB_PATH=/data/reels_tracker.db PYTHONUNBUFFERED=1
CMD ["python", "tracker.py", "--config", "/data/config.json"]

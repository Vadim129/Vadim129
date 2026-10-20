FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# Вырезание фона нужно почти всегда — ставим сразу. Убрать строку, если образ нужен лёгкий.
COPY requirements-rembg.txt .
RUN pip install --no-cache-dir -r requirements-rembg.txt

COPY . .
# PORT нужен Cloudflare Containers (healthcheck + пробуждение контейнера).
# На обычном сервере поллинг работает и без HTTP — порт просто не мешает.
ENV PORT=8080 DATA_DIR=/app/data
EXPOSE 8080
CMD ["python", "bot.py"]

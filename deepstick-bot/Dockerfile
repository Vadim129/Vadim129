FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# Вырезание фона нужно почти всегда — ставим сразу. Убрать строку, если образ нужен лёгкий.
COPY requirements-rembg.txt .
RUN pip install --no-cache-dir -r requirements-rembg.txt

COPY . .
CMD ["python", "bot.py"]

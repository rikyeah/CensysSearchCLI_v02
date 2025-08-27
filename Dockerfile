```
# Dockerfile for Censys CLI with Python and Node.js support
# Includes Playwright for browser automation and SQLite for state persistence
FROM node:20-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv sqlite3 git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
COPY requirements.txt ./

RUN npm install --omit=dev \
 && pip3 install --no-cache-dir -r requirements.txt

RUN npx playwright install --with-deps chromium

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

RUN mkdir -p out logs

ENTRYPOINT ["python3", "main.py"]
```
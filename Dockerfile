FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 DB_PATH=/app/data/flights.db \
    NTFY_ENABLED=false TELEGRAM_ENABLED=false
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 radar
COPY --chown=radar:radar . .
RUN mkdir -p /app/data && chown -R radar:radar /app/data
USER radar
EXPOSE 8787
CMD ["python", "main.py", "server"]

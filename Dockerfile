FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 DB_PATH=/app/data/flights.db \
    DEPLOYMENT_MODE=public AUTOSCAN_ENABLED=false \
    NTFY_ENABLED=false TELEGRAM_ENABLED=false
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 radar
COPY --chown=radar:radar . .
RUN mkdir -p /app/data && chown radar:radar /app/data
USER radar
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT',os.getenv('API_PORT','8787'))+'/api/health',timeout=4)"
CMD ["python", "deploy/start.py"]

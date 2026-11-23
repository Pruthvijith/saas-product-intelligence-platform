FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src/ src/
COPY scripts/ scripts/
RUN python -m pip install --no-cache-dir . && useradd -r -u 10001 portfolio && mkdir /data && chown portfolio /data
USER portfolio
ENV PRODUCT_DB=/data/events.sqlite
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "product_intelligence.api:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 THREAD_DATA_DIR=/data
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 thread && mkdir /data && chown thread:thread /data
USER thread
EXPOSE 8766
VOLUME /data
CMD ["python", "-m", "uvicorn", "thread_voice.server:app", "--host", "0.0.0.0", "--port", "8766"]

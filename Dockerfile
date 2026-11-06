FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py security.py archives.py evidence_store.py chart_config.py ./
COPY static ./static
RUN mkdir data && chown -R 10001:10001 /app
USER 10001
ENV HOST=0.0.0.0 PORT=8000 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python", "server.py"]

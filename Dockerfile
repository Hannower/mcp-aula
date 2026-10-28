FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# As dependências pertencem ao próprio servidor MCP.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY server.py server_http.py ./
EXPOSE 8001
CMD ["python", "server_http.py"]

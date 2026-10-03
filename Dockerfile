FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

COPY requirements-docker.txt .

RUN pip install --no-cache-dir -r requirements-docker.txt

COPY app.py .
COPY src ./src
COPY data/policy ./data/policy

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]

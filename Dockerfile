FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV SECRET_KEY=change-me
ENV FLASK_DEBUG=false
ENV ADMIN_PASSWORD=admin123

CMD ["python", "run.py"]

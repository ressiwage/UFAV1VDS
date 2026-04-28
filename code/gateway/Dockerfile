FROM python:3.12-slim

# Системные зависимости для mysql-connector и libaom runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    libgomp1 \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN ldconfig

WORKDIR /app


COPY gateway/requirements.txt .
RUN pip install -r requirements.txt

COPY _shared/ ./_shared/
COPY gateway/ .


EXPOSE 7995

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7995", "--log-level", "debug"]
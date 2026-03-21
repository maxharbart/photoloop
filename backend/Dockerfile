FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache \
    libheif-dev jpeg-dev ffmpeg \
    gcc musl-dev linux-headers libffi-dev

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

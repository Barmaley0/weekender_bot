FROM python:3.11-slim

WORKDIR /app

VOLUME D:\Developer\weekender_bot:/app/database

RUN python -m pip install --upgrade pip

COPY requirements.txt /app

RUN python -m pip install -r requirements.txt

COPY . /app

CMD ["python", "main.py"]


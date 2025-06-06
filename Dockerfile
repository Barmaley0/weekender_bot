FROM python:3.11-slim

WORKDIR /app

RUN python -m pip install --upgrade pip --no-cache-dir

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.bot.main"]


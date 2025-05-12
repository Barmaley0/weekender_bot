FROM python:3.11-slim

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY requirements.txt /app

COPY main.py .
COPY app/ ./app/
COPY alembic.ini .
COPY migrations/ ./migrations/
COPY env.py ./migrations/

RUN python -m pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]


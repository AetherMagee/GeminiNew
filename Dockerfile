FROM python:3.12-slim
LABEL authors="Aether"
WORKDIR /bot
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["python3", "/bot/main.py"]
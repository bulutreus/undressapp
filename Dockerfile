# Mini App + API: uvicorn (PORT ortam deÄŸiÅŸkeni, Render/Fly/Railway uyumlu)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py bot.py telegram_init_data.py ./
COPY __pycache__/bot.cpython-312.pyc ./__pycache__/
COPY miniapp ./miniapp
COPY assets ./assets
COPY data/card_prompts.txt ./data/card_prompts.txt
COPY CloLessAi.json ./
# Workflow ve Ã§Ä±ktÄ± yolu; container iÃ§inde aynÄ± isim
ENV COMFY_WORKFLOW_PATH=/app/CloLessAi.json
ENV COMFY_OUTPUT_DIR=/app/outputs
ENV BOT_DATA_DIR=/app/data

RUN mkdir -p /app/outputs /app/data

EXPOSE 8080

CMD sh -c 'uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}'



#!/bin/bash
echo "Parando instancias anteriores..."
pkill -f "telegram_bot.py" || true
sleep 3

echo "Limpando webhook do Telegram..."
python3 -c "
import os, requests
token = os.environ.get('TELEGRAM_TOKEN', '')
if token:
    r = requests.get(f'https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true')
    print('deleteWebhook:', r.json())
"

sleep 2
echo "Iniciando bot..."
exec python bot/telegram_bot.py

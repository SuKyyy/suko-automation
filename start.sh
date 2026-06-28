#!/bin/bash
# Mata qualquer instância anterior do bot antes de subir
echo "Parando instâncias anteriores..."
pkill -f "telegram_bot.py" || true
sleep 2
echo "Iniciando bot..."
exec python bot/telegram_bot.py

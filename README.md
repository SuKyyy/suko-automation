# SuKo-9000 BLACK EDITION

Telegram Bot + Stealth Browser Automation para criar contas ChatGPT.

## Arquitetura

```
Telegram Bot (Render)  ←→  Neon DB  ←→  Worker (seu PC)
```

- **Render** → roda `bot/telegram_bot.py` (recebe comandos, salva pool, recebe códigos)
- **Seu PC** → roda `bot/worker.py` (abre browser, faz automação)
- **Neon** → banco de dados compartilhado entre os dois

## Setup

### 1. Variáveis de ambiente
Copie `.env.example` para `.env` e preencha:
```
TELEGRAM_TOKEN=seu_token
DATABASE_URL=sua_connection_string_neon
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Rodar o bot (ou deploy no Render)
```bash
python bot/telegram_bot.py
```

### 4. Rodar o worker no PC (quando quiser iniciar um job)
```bash
python bot/worker.py
```

## Comandos do Bot

| Comando | Descrição |
|---|---|
| `/add email senha` | Adiciona email na pool |
| `/pool` | Lista emails pendentes |
| `/clear` | Limpa a pool |
| `/start_job` | Cria um job (rode o worker depois) |
| `/status` | Status atual |
| `/resultados` | Últimos resultados |

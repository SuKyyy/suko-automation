import os
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from db import (
    init_db, add_to_pool, get_pool, clear_pool,
    get_active_job, create_job, save_codigo,
    is_waiting_code, get_resultados
)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("📋 Ver Pool", callback_data="pool"),
         InlineKeyboardButton("➕ Adicionar Conta", callback_data="add")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="clear"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")],
        [InlineKeyboardButton("📈 Resultados", callback_data="resultados")],
    ]
    return InlineKeyboardMarkup(keyboard)

def parece_conta(linha):
    """Retorna True se a linha tem cara de email:senha:nome"""
    partes = linha.split(":")
    if len(partes) < 3:
        return False
    email = partes[0].strip()
    return "@" in email and "." in email

def processar_contas(linhas):
    """Processa lista de linhas no formato email:senha:nome. Retorna (adicionadas, erros)."""
    adicionadas = []
    erros = []
    for linha in linhas:
        if not linha.strip():
            continue
        partes = linha.split(":")
        if len(partes) < 3:
            erros.append(f"`{linha}` — formato inválido (use email:senha:nome)")
            continue

        email = partes[0].strip()
        senha = partes[1].strip()
        nome = ":".join(partes[2:]).strip()

        if not email or not senha or not nome:
            erros.append(f"`{linha}` — campo vazio")
            continue

        if "@" not in email:
            erros.append(f"`{linha}` — email inválido")
            continue

        ano = datetime.date.today().year - 22
        mes = random.randint(1, 12)
        max_dia = [31,28,31,30,31,30,31,31,30,31,30,31][mes-1]
        dia = random.randint(1, max_dia)
        nascimento = f"{dia:02d}/{mes:02d}/{ano}"

        add_to_pool(email, senha, nome, nascimento)
        adicionadas.append(f"`{email}` | {nome}")

    return adicionadas, erros

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text(
        "🤖 *SuKo-9000 BLACK EDITION*\n\nSeleciona o que queres fazer:",
        parse_mode="Markdown",
        reply_markup=menu_principal()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 *Menu Principal*", parse_mode="Markdown", reply_markup=menu_principal())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "pool":
        pool = get_pool()
        if not pool:
            texto = "📋 *Pool vazia.*\n\nManda direto no chat: `email:senha:Nome`"
        else:
            texto = f"📋 *Pool ({len(pool)} pendentes):*\n\n"
            for i, c in enumerate(pool, 1):
                texto += f"{i}. `{c['email']}` | {c.get('nome','?')}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

    elif data == "add":
        await query.edit_message_text(
            "➕ *Adicionar conta*\n\n"
            "Manda no formato:\n"
            "`email:senha:Nome Completo`\n\n"
            "Exemplos:\n"
            "`teste@gmail.com:Senha123:João Silva`\n"
            "`outro@gmail.com:Pass456:Tony`\n\n"
            "Pode mandar várias de uma vez, uma por linha.\n"
            "_A data de nascimento é gerada automaticamente._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="pool")]])
        )

    elif data == "clear":
        clear_pool()
        await query.edit_message_text("🗑️ Pool limpa!", reply_markup=menu_principal())

    elif data == "status":
        pool = get_pool()
        active = get_active_job()
        waiting = is_waiting_code(chat_id)
        texto = (
            f"📊 *Status:*\n\n"
            f"• Contas pendentes: `{len(pool)}`\n"
            f"• Job ativo: {'✅' if active else '❌'}\n"
            f"• Aguardando código: {'✅' if waiting else '❌'}"
        )
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

    elif data == "start_job":
        pool = get_pool()
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_principal())
            return
        if get_active_job():
            await query.edit_message_text("⚠️ Já tem um job rodando!", reply_markup=menu_principal())
            return
        create_job(chat_id)
        await query.edit_message_text(
            f"🚀 *Job criado!* {len(pool)} conta(s) na fila.\n\nRode no PC: `python worker.py`",
            parse_mode="Markdown", reply_markup=menu_principal()
        )

    elif data == "resultados":
        rows = get_resultados()
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 *Últimos Resultados:*\n\n"
            for r in rows:
                emoji = "✅" if r["status"] == "SUCESSO" else ("⚠️" if r["status"] == "VERIFICAR" else "❌")
                texto += f"{emoji} `{r['email']}` → {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Código de verificação tem prioridade
    if is_waiting_code(chat_id):
        # Só salva como código se não parecer uma conta
        if not parece_conta(text.splitlines()[0]):
            save_codigo(chat_id, text.strip())
            await update.message.reply_text("✅ Código salvo! O worker vai pegar automaticamente.")
            return

    # Detecta automaticamente se é conta(s) no formato email:senha:nome
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    if any(parece_conta(l) for l in linhas):
        adicionadas, erros = processar_contas(linhas)

        resposta = ""
        if adicionadas:
            resposta += f"✅ *{len(adicionadas)} conta(s) adicionada(s):*\n" + "\n".join(adicionadas) + "\n"
        if erros:
            resposta += f"\n❌ *{len(erros)} erro(s):*\n" + "\n".join(erros)

        await update.message.reply_text(
            resposta.strip(),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Ver Pool", callback_data="pool"),
                InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")
            ]])
        )
        return

    # Fallback: mostra menu
    await update.message.reply_text("🤖 Usa os botões abaixo:", reply_markup=menu_principal())

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 SuKo-9000 Telegram Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()

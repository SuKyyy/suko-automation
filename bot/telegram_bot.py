import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from db import (
    init_db, add_to_pool, get_pool, clear_pool,
    get_active_job, create_job, save_codigo,
    is_waiting_code, get_resultados
)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text(
        "🤖 *SuKo-9000 BLACK EDITION*\n\n"
        "Comandos:\n"
        "`/add email senha` → adiciona email na pool\n"
        "`/pool` → mostra emails na fila\n"
        "`/clear` → limpa a pool\n"
        "`/start_job` → dispara o worker (rode no PC)\n"
        "`/status` → status atual\n"
        "`/resultados` → últimos resultados",
        parse_mode="Markdown"
    )

async def add_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Uso: `/add email@exemplo.com senha123`", parse_mode="Markdown")
        return
    email = context.args[0]
    senha = " ".join(context.args[1:])
    add_to_pool(email, senha)
    await update.message.reply_text(f"✅ Adicionado: `{email}`", parse_mode="Markdown")

async def show_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = get_pool()
    if not pool:
        await update.message.reply_text("Pool vazia. Usa `/add` pra adicionar contas.", parse_mode="Markdown")
        return
    texto = "📋 *Pool de Emails (pending):*\n\n"
    for i, c in enumerate(pool, 1):
        texto += f"{i}. `{c['email']}`\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def clear_pool_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_pool()
    await update.message.reply_text("🗑️ Pool limpa!")

async def start_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = get_pool()
    if not pool:
        await update.message.reply_text("Pool vazia. Adiciona contas com `/add`", parse_mode="Markdown")
        return
    active = get_active_job()
    if active:
        await update.message.reply_text("⚠️ Já tem um job rodando! Aguarda terminar ou reinicia o worker.")
        return
    chat_id = update.effective_chat.id
    create_job(chat_id)
    await update.message.reply_text(
        f"🚀 Job criado! {len(pool)} conta(s) na fila.\n\n"
        f"Agora rode `python bot/worker.py` no seu PC para começar.",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = get_pool()
    active = get_active_job()
    chat_id = update.effective_chat.id
    waiting = is_waiting_code(chat_id)
    await update.message.reply_text(
        f"📊 *Status:*\n"
        f"• Contas pendentes: {len(pool)}\n"
        f"• Job ativo: {'✅ Sim' if active else '❌ Não'}\n"
        f"• Aguardando código: {'✅ Sim' if waiting else '❌ Não'}",
        parse_mode="Markdown"
    )

async def resultados_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_resultados()
    if not rows:
        await update.message.reply_text("Nenhum resultado ainda.")
        return
    texto = "📈 *Últimos Resultados:*\n\n"
    for r in rows:
        emoji = "✅" if r["status"] == "SUCESSO" else "❌"
        texto += f"{emoji} `{r['email']}` → {r['status']}\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if is_waiting_code(chat_id):
        save_codigo(chat_id, text)
        await update.message.reply_text("✅ Código salvo! O worker vai pegar automaticamente.")
    else:
        await update.message.reply_text("Nenhum código esperado agora. Usa os comandos do menu.")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_email))
    app.add_handler(CommandHandler("pool", show_pool))
    app.add_handler(CommandHandler("clear", clear_pool_cmd))
    app.add_handler(CommandHandler("start_job", start_job))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("resultados", resultados_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 SuKo-9000 Telegram Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()

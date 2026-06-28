import os
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
         InlineKeyboardButton("➕ Adicionar Email", callback_data="add")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="clear"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")],
        [InlineKeyboardButton("📈 Resultados", callback_data="resultados")],
    ]
    return InlineKeyboardMarkup(keyboard)

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
            texto = "📋 *Pool vazia.*\n\nUsa ➕ Adicionar Email pra colocar contas."
        else:
            texto = f"📋 *Pool ({len(pool)} pendentes):*\n\n"
            for i, c in enumerate(pool, 1):
                texto += f"{i}. `{c['email']}` | {c.get('nome','?')} | {c.get('nascimento','?')}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

    elif data == "add":
        context.user_data["aguardando"] = "add"
        await query.edit_message_text(
            "➕ *Adicionar conta*\n\n"
            "Manda no formato:\n"
            "`email senha Nome Completo DD/MM/AAAA`\n\n"
            "Exemplo:\n"
            "`teste@gmail.com Senha123 Jo\u00e3o Silva 15/03/1995`",
            parse_mode="Markdown"
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
            f"• Aguardando c\u00f3digo: {'✅' if waiting else '❌'}"
        )
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

    elif data == "start_job":
        pool = get_pool()
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_principal())
            return
        if get_active_job():
            await query.edit_message_text("⚠️ J\u00e1 tem um job rodando!", reply_markup=menu_principal())
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
            texto = "📈 *\u00daltimos Resultados:*\n\n"
            for r in rows:
                emoji = "✅" if r["status"] == "SUCESSO" else ("⚠️" if r["status"] == "VERIFICAR" else "❌")
                texto += f"{emoji} `{r['email']}` \u2192 {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_principal())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if context.user_data.get("aguardando") == "add":
        parts = text.split()
        # Formato: email senha Nome... DD/MM/AAAA
        # A data sempre é o último token
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ Formato inv\u00e1lido. Exemplo:\n`teste@gmail.com Senha123 Jo\u00e3o Silva 15/03/1995`",
                parse_mode="Markdown"
            )
            return

        email = parts[0]
        senha = parts[1]
        nascimento = parts[-1]  # último token = data
        nome = " ".join(parts[2:-1])  # tudo entre senha e data = nome

        if not nome:
            await update.message.reply_text(
                "❌ Precisa do nome completo.\nExemplo:\n`teste@gmail.com Senha123 Jo\u00e3o Silva 15/03/1995`",
                parse_mode="Markdown"
            )
            return

        add_to_pool(email, senha, nome, nascimento)
        context.user_data["aguardando"] = None
        await update.message.reply_text(
            f"✅ Adicionado:\n`{email}` | {nome} | {nascimento}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Adicionar outro", callback_data="add"),
                InlineKeyboardButton("🏠 Menu", callback_data="pool")
            ]])
        )
        return

    if is_waiting_code(chat_id):
        save_codigo(chat_id, text)
        await update.message.reply_text("✅ C\u00f3digo salvo! O worker vai pegar automaticamente.")
        return

    await update.message.reply_text("🤖 Usa os bot\u00f5es abaixo:", reply_markup=menu_principal())

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

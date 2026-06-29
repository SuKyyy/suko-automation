import os
import random
import datetime
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import Conflict
from db import (
    init_db, get_or_create_user, get_user, is_admin, get_all_users,
    ajustar_saldo, get_preco, set_preco,
    add_to_pool, get_pool, get_pool_all_status, clear_pool,
    get_active_job, get_all_active_jobs, create_job, cancel_jobs,
    save_codigo, is_waiting_code, get_resultados
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
fragmento_buffer = {}

def gerar_nascimento():
    ano = datetime.date.today().year - 22
    mes = random.randint(1, 12)
    max_dia = [31,28,31,30,31,30,31,31,30,31,30,31][mes-1]
    dia = random.randint(1, max_dia)
    return f"{dia:02d}/{mes:02d}/{ano}"

def parse_conta(texto):
    texto = texto.strip()
    if not texto or "@" not in texto:
        return None
    if ":" in texto:
        partes = texto.split(":", 2)
        if len(partes) == 3:
            email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
            if "@" in email and "." in email and senha and nome:
                return email, senha, nome
    partes = texto.split(None, 2)
    if len(partes) == 3:
        email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
        if "@" in email and "." in email and senha and nome:
            return email, senha, nome
    return None

def processar_texto(user_id, text):
    adicionadas = []
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    for linha in linhas:
        resultado = parse_conta(linha)
        if resultado:
            email, senha, nome = resultado
            add_to_pool(user_id, email, senha, nome, gerar_nascimento())
            adicionadas.append(f"{email} | {nome}")
    return adicionadas, None

def menu_admin():
    keyboard = [
        [InlineKeyboardButton("👥 Usuários", callback_data="adm_usuarios")],
        [InlineKeyboardButton("🌐 Pool Global", callback_data="adm_pool")],
        [InlineKeyboardButton("⚙️ Jobs Ativos", callback_data="adm_jobs")],
        [InlineKeyboardButton("📈 Resultados", callback_data="adm_resultados")],
        [InlineKeyboardButton("💰 Preço", callback_data="adm_preco")],
        [InlineKeyboardButton("💰 Dar Saldo", callback_data="adm_dar_saldo")],
        [InlineKeyboardButton("➖ Tirar Saldo", callback_data="adm_tirar_saldo")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="adm_clear_pool")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_usuario():
    keyboard = [
        [InlineKeyboardButton("📋 Pool", callback_data="pool")],
        [InlineKeyboardButton("➕ Adicionar Conta", callback_data="add")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="clear")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")],
        [InlineKeyboardButton("📈 Resultados", callback_data="resultados")],
        [InlineKeyboardButton("👤 Perfil", callback_data="perfil")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_voltar_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Voltar", callback_data="adm_menu")]])

def menu_voltar_user():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="menu_user")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nome = update.effective_user.first_name or ''
    user = get_or_create_user(chat_id, nome)
    if is_admin(chat_id):
        await update.message.reply_text(
            f"👑 *Admin Panel* — Bem vindo, {nome}!",
            parse_mode="Markdown",
            reply_markup=menu_admin()
        )
    else:
        preco = get_preco()
        await update.message.reply_text(
            f"🤖 *SuKo-9000*\n\n"
            f"💰 Saldo: R$ {user['saldo']:.2f}\n"
            f"💲 Preço por conta: R$ {preco:.2f}\n\n"
            f"Adicione saldo com um admin para começar.",
            parse_mode="Markdown",
            reply_markup=menu_usuario()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    user = get_user(chat_id)
    if not user:
        await query.edit_message_text("Usa /start primeiro.")
        return

    # Aqui vai todo o código do button_handler que você tinha antes
    # (copie do seu arquivo anterior se tiver)
    if data == "adm_menu":
        await query.edit_message_text("👑 *Admin Panel*", parse_mode="Markdown", reply_markup=menu_admin())
    # ... (adicione o resto do seu button_handler aqui)

    elif data == "menu_user":
        await query.edit_message_text("🤖 *Menu*", parse_mode="Markdown", reply_markup=menu_usuario())

    # Continue com todos os elifs que você tinha...

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    user = get_or_create_user(chat_id, update.effective_user.first_name or '')

    logger.info(f"[MSG] {chat_id} | {repr(text)}")

    aguardando = context.user_data.get('aguardando')

    # Aqui vai todo o código do handle_message que você tinha antes
    # (copie do seu arquivo anterior)

    if is_admin(chat_id):
        await update.message.reply_text("👑 Admin Panel:", reply_markup=menu_admin())
    else:
        await update.message.reply_text("🤖 Menu:", reply_markup=menu_usuario())

async def run_bot():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("Webhook antigo removido.")
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()

    retry = 0
    while True:
        try:
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("🤖 SuKo-9000 rodando!")
            break
        except Conflict:
            retry += 1
            wait = min(10 * retry, 60)
            logger.warning(f"Conflito. Aguardando {wait}s...")
            await asyncio.sleep(wait)

    await asyncio.Event().wait()

def main():
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()

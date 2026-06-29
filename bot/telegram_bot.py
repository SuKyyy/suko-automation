import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_or_create_user(chat_id, nome):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE chat_id=%s", (chat_id,))
            user = cur.fetchone()
            if not user:
                cur.execute("INSERT INTO usuarios (chat_id, nome) VALUES (%s, %s) RETURNING *", (chat_id, nome))
                user = cur.fetchone()
            return user

def add_to_pool(user_id, email, senha, nome, nascimento):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pool (user_id, email, senha, nome, nascimento, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                ON CONFLICT (email) DO NOTHING
            """, (user_id, email, senha, nome, nascimento))
        conn.commit()

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
            add_to_pool(user_id, email, senha, nome, "01/01/2000")
            adicionadas.append(f"{email} | {nome}")
    return adicionadas

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot iniciado. Manda as contas no formato email:senha:Nome Completo (uma por linha)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    user = get_or_create_user(chat_id, update.effective_user.first_name or "")

    if "@" in text:
        adicionadas = processar_texto(chat_id, text)
        if adicionadas:
            resposta = f"\u2705 {len(adicionadas)} conta(s) adicionada(s):\n" + "\n".join(adicionadas)
            await update.message.reply_text(resposta)
        else:
            await update.message.reply_text("Nenhuma conta válida encontrada. Use o formato:\nemail:senha:Nome Completo")
        return

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Telegram bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()

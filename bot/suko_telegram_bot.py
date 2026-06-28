import os
import json
import time
import random
import threading
import queue
from datetime import datetime

from cloakbrowser import launch
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIG ====================
TOKEN = "SEU_TOKEN_AQUI"          # <--- COLA TEU TOKEN AQUI
CHAT_ID = None                     # vai preencher sozinho quando tu mandar /start

POOL_FILE = "email_pool.json"
RESULTS_FILE = "resultados_chatgpt.txt"

code_queue = queue.Queue()
waiting_for_code = False
current_email = ""
automation_running = False

# ==================== FUNÇÕES DO AUTOMATION ====================
def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def safe_click(page, text, timeout=12000):
    try:
        page.get_by_text(text, exact=False).first.click(timeout=timeout)
        return True
    except: pass
    try:
        page.click(f"text={text}", timeout=timeout)
        return True
    except: pass
    try:
        page.locator(f"button:has-text('{text}')").first.click(timeout=timeout)
        return True
    except: return False

def safe_fill(page, selector, value, timeout=8000):
    try:
        page.locator(selector).first.fill(value, timeout=timeout)
        return True
    except:
        try:
            page.fill(selector, value, timeout=timeout)
            return True
        except: return False

def log_result(email, status):
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {email} | {status}\n")

def load_pool():
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_pool(pool):
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)

# ==================== AUTOMATION THREAD ====================
def run_automation(pool, bot_app):
    global waiting_for_code, current_email, automation_running
    automation_running = True

    browser = launch(headless=False, humanize=True)

    for conta in pool:
        email = conta["email"]
        senha = conta["senha"]
        current_email = email

        print(f"\n=== Criando: {email} ===")
        bot_app.bot.send_message(chat_id=CHAT_ID, text=f"🚀 Iniciando conta: {email}")

        page = browser.new_page()
        try:
            page.goto("https://chatgpt.com")
            page.wait_for_load_state("networkidle")
            human_delay()

            if not safe_click(page, "Cadastre-se gratuitamente"):
                safe_click(page, "Sign up for free")
            human_delay(2, 4)

            for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
                if safe_fill(page, sel, email): break
            page.keyboard.press("Enter")
            human_delay(2.5, 4.5)

            try:
                page.wait_for_selector("input[type='password']", timeout=6000)
                safe_fill(page, "input[type='password']", senha)
                page.keyboard.press("Enter")
            except:
                pass

            # === PEDIR CÓDIGO PELO TELEGRAM ===
            waiting_for_code = True
            bot_app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"📩 Conta **{email}** precisa do código de verificação.\n\nMe responde **só com o código de 6 dígitos**."
            )

            try:
                code = code_queue.get(timeout=300)  # espera até 5 minutos
                # Tenta preencher o código (ajusta o seletor se mudar)
                try:
                    page.fill("input[placeholder*='code' i], input[name*='code' i], input[type='text']", code)
                    page.keyboard.press("Enter")
                except:
                    page.keyboard.type(code)
                    page.keyboard.press("Enter")

                bot_app.bot.send_message(chat_id=CHAT_ID, text="✅ Código recebido e colado!")
            except queue.Empty:
                bot_app.bot.send_message(chat_id=CHAT_ID, text="⏰ Timeout esperando o código. Pulando essa conta.")
                log_result(email, "TIMEOUT_CODIGO")
                continue

            waiting_for_code = False

            # Checa se logou
            try:
                page.wait_for_selector("text=ChatGPT", timeout=10000)
                bot_app.bot.send_message(chat_id=CHAT_ID, text=f"✅ Conta {email} criada com sucesso!")
                log_result(email, "SUCESSO")
            except:
                bot_app.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {email} pode precisar de verificação manual.")
                log_result(email, "VERIFICAR")

        except Exception as e:
            bot_app.bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro em {email}: {str(e)[:100]}")
            log_result(email, f"ERRO - {e}")
        finally:
            page.close()
            human_delay(5, 8)

    browser.close()
    automation_running = False
    bot_app.bot.send_message(chat_id=CHAT_ID, text="🏁 Job finalizado! Todas as contas processadas.")

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    await update.message.reply_text(
        "🤖 SuKo-9000 BLACK EDITION - Telegram Bot\n\n"
        "Comandos:\n"
        "/add email senha → adiciona na pool\n"
        "/pool → mostra emails cadastrados\n"
        "/start_job → começa a criar as contas\n"
        "/status → status atual"
    )

async def add_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /add email@exemplo.com senha123")
        return

    email = context.args[0]
    senha = " ".join(context.args[1:])

    pool = load_pool()
    pool.append({"email": email, "senha": senha})
    save_pool(pool)

    await update.message.reply_text(f"✅ Adicionado: {email}")

async def show_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = load_pool()
    if not pool:
        await update.message.reply_text("Pool vazia. Usa /add pra adicionar contas.")
        return

    texto = "📋 Pool de Emails:\n\n"
    for i, c in enumerate(pool, 1):
        texto += f"{i}. {c['email']}\n"
    await update.message.reply_text(texto)

async def start_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global automation_running
    if automation_running:
        await update.message.reply_text("⚠️ Já tem um job rodando.")
        return

    pool = load_pool()
    if not pool:
        await update.message.reply_text("Pool vazia. Adiciona contas primeiro com /add")
        return

    await update.message.reply_text(f"🚀 Iniciando criação de {len(pool)} contas...")

    # Roda o automation em thread separada
    thread = threading.Thread(target=run_automation, args=(pool, context.application), daemon=True)
    thread.start()

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_for_code
    if waiting_for_code:
        code = update.message.text.strip()
        code_queue.put(code)
        waiting_for_code = False
        await update.message.reply_text("✅ Código recebido! Continuando...")
    else:
        await update.message.reply_text("Nenhum código esperado no momento. Usa os comandos normais.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = load_pool()
    await update.message.reply_text(
        f"📊 Status:\n"
        f"• Contas na pool: {len(pool)}\n"
        f"• Job rodando: {'Sim' if automation_running else 'Não'}\n"
        f"• Aguardando código: {'Sim' if waiting_for_code else 'Não'}"
    )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_email))
    app.add_handler(CommandHandler("pool", show_pool))
    app.add_handler(CommandHandler("start_job", start_job))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    print("🤖 SuKo-9000 Telegram Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
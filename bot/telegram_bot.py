import os
import random
import datetime
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import Conflict
from db import (
    init_db, add_to_pool, get_pool, clear_pool,
    get_active_job, create_job, save_codigo,
    is_waiting_code, get_resultados
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Buffer por chat para juntar fragmentos de mensagem
fragmento_buffer = {}

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

def gerar_nascimento():
    ano = datetime.date.today().year - 22
    mes = random.randint(1, 12)
    max_dia = [31,28,31,30,31,30,31,31,30,31,30,31][mes-1]
    dia = random.randint(1, max_dia)
    return f"{dia:02d}/{mes:02d}/{ano}"

def parse_conta(texto):
    """
    Tenta extrair (email, senha, nome) de um texto qualquer.
    Divide sempre nas primeiras 2 ocorrencias de : para nao quebrar senha/nome.
    Retorna (email, senha, nome) ou None.
    """
    texto = texto.strip()
    if not texto or "@" not in texto:
        return None

    # Divide nas primeiras 2 ocorrencias de :
    partes = texto.split(":", 2)
    if len(partes) == 3:
        email = partes[0].strip()
        senha = partes[1].strip()
        nome = partes[2].strip()
        if "@" in email and "." in email and senha and nome:
            return email, senha, nome

    # Tenta com espaco como separador
    partes = texto.split(None, 2)  # split por qualquer whitespace
    if len(partes) == 3:
        email = partes[0].strip()
        senha = partes[1].strip()
        nome = partes[2].strip()
        if "@" in email and "." in email and senha and nome:
            return email, senha, nome

    return None

def processar_texto(text):
    """Processa uma ou mais linhas, retorna (adicionadas, erros, sobrou_fragmento)."""
    adicionadas = []
    erros = []
    fragmento = None

    linhas = [l.strip() for l in text.splitlines() if l.strip()]

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        resultado = parse_conta(linha)
        if resultado:
            email, senha, nome = resultado
            add_to_pool(email, senha, nome, gerar_nascimento())
            adicionadas.append(f"{email} | {nome}")
            i += 1
        elif "@" in linha:
            # Tem email mas nao fechou — pode ser fragmento quebrado pelo Telegram
            # Tenta juntar com a proxima linha
            if i + 1 < len(linhas):
                junto = linha + linhas[i+1]
                resultado = parse_conta(junto)
                if resultado:
                    email, senha, nome = resultado
                    add_to_pool(email, senha, nome, gerar_nascimento())
                    adicionadas.append(f"{email} | {nome}")
                    i += 2
                    continue
            # Guarda como fragmento para a proxima mensagem
            fragmento = linha
            i += 1
        else:
            # Linha sem @ — pode ser continuacao de fragmento anterior
            i += 1

    return adicionadas, erros, fragmento

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text(
        "🤖 SuKo-9000 BLACK EDITION\n\nSeleciona o que queres fazer:",
        reply_markup=menu_principal()
    )

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Menu Principal", reply_markup=menu_principal())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "pool":
        pool = get_pool()
        if not pool:
            texto = "📋 Pool vazia.\n\nManda direto: email:senha:Nome"
        else:
            texto = f"📋 Pool ({len(pool)} pendentes):\n\n"
            for i, c in enumerate(pool, 1):
                texto += f"{i}. {c['email']} | {c.get('nome','?')}\n"
        await query.edit_message_text(texto, reply_markup=menu_principal())

    elif data == "add":
        await query.edit_message_text(
            "➕ Adicionar conta\n\n"
            "Manda no formato:\n"
            "email:senha:Nome Completo\n\n"
            "Pode mandar varias de uma vez, uma por linha.\n"
            "A data de nascimento e gerada automaticamente.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="pool")]])
        )

    elif data == "clear":
        clear_pool()
        fragmento_buffer.clear()
        await query.edit_message_text("🗑️ Pool limpa!", reply_markup=menu_principal())

    elif data == "status":
        pool = get_pool()
        active = get_active_job()
        waiting = is_waiting_code(chat_id)
        texto = (
            f"📊 Status:\n\n"
            f"Contas pendentes: {len(pool)}\n"
            f"Job ativo: {'sim' if active else 'nao'}\n"
            f"Aguardando codigo: {'sim' if waiting else 'nao'}"
        )
        await query.edit_message_text(texto, reply_markup=menu_principal())

    elif data == "start_job":
        pool = get_pool()
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_principal())
            return
        if get_active_job():
            await query.edit_message_text("⚠️ Ja tem um job rodando!", reply_markup=menu_principal())
            return
        create_job(chat_id)
        await query.edit_message_text(
            f"🚀 Job criado! {len(pool)} conta(s) na fila.\n\nRode no PC: python worker.py",
            reply_markup=menu_principal()
        )

    elif data == "resultados":
        rows = get_resultados()
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 Ultimos Resultados:\n\n"
            for r in rows:
                emoji = "✅" if r["status"] == "SUCESSO" else ("⚠️" if r["status"] == "VERIFICAR" else "❌")
                texto += f"{emoji} {r['email']} -> {r['status']}\n"
        await query.edit_message_text(texto, reply_markup=menu_principal())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    logger.info(f"[MSG] chat_id={chat_id} | texto={repr(text)}")

    # Codigo de verificacao (so numeros, sem @)
    if is_waiting_code(chat_id) and "@" not in text:
        save_codigo(chat_id, text.strip())
        await update.message.reply_text("✅ Codigo salvo! O worker vai pegar automaticamente.")
        return

    # Se tem @ ou tem fragmento pendente, tenta processar como conta
    tem_fragmento = chat_id in fragmento_buffer
    if "@" in text or tem_fragmento:
        # Junta fragmento anterior se existir
        if tem_fragmento:
            texto_completo = fragmento_buffer.pop(chat_id) + text
            logger.info(f"[FRAGMENTO] Juntando: {repr(texto_completo)}")
        else:
            texto_completo = text

        adicionadas, erros, fragmento = processar_texto(texto_completo)

        # Guarda fragmento para proxima mensagem
        if fragmento:
            fragmento_buffer[chat_id] = fragmento
            logger.info(f"[FRAGMENTO] Guardando: {repr(fragmento)}")

        if adicionadas:
            resposta = f"✅ {len(adicionadas)} conta(s) adicionada(s):\n" + "\n".join(adicionadas)
            if fragmento:
                resposta += "\n\n⏳ Aguardando continuacao da ultima conta..."
            await update.message.reply_text(
                resposta,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Ver Pool", callback_data="pool"),
                    InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")
                ]])
            )
            return
        elif fragmento:
            # So tem fragmento, aguarda proxima mensagem silenciosamente
            return
        elif erros:
            await update.message.reply_text("❌ Nao consegui processar:\n" + "\n".join(erros))
            return

    await update.message.reply_text("Usa os botoes abaixo:", reply_markup=menu_principal())

async def run_bot():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()

    retry = 0
    while True:
        try:
            logger.info(f"Iniciando polling (tentativa {retry + 1})...")
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

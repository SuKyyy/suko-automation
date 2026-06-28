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
fragmento_buffer = {}

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("\U0001f4cb Ver Pool", callback_data="pool"),
         InlineKeyboardButton("\u2795 Adicionar Conta", callback_data="add")],
        [InlineKeyboardButton("\U0001f5d1\ufe0f Limpar Pool", callback_data="clear"),
         InlineKeyboardButton("\U0001f4ca Status", callback_data="status")],
        [InlineKeyboardButton("\U0001f680 Iniciar Job", callback_data="start_job")],
        [InlineKeyboardButton("\U0001f4c8 Resultados", callback_data="resultados")],
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
    Tenta extrair (email, senha, nome) de um texto.
    Suporta separador : ou espaco.
    """
    texto = texto.strip()
    if not texto or "@" not in texto:
        return None

    # Separador : (divide so nas primeiras 2 ocorrencias)
    if ":" in texto:
        partes = texto.split(":", 2)
        if len(partes) == 3:
            email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
            if "@" in email and "." in email and senha and nome:
                logger.info(f"[PARSE] ok via ':' -> {email} | {nome}")
                return email, senha, nome

    # Separador espaco
    partes = texto.split(None, 2)
    if len(partes) == 3:
        email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
        if "@" in email and "." in email and senha and nome:
            logger.info(f"[PARSE] ok via espaco -> {email} | {nome}")
            return email, senha, nome

    return None

def processar_texto(text):
    adicionadas = []
    erros = []
    fragmento = None

    # Primeiro tenta a mensagem inteira (caso venha numa so linha)
    resultado = parse_conta(text)
    if resultado:
        email, senha, nome = resultado
        add_to_pool(email, senha, nome, gerar_nascimento())
        return [f"{email} | {nome}"], [], None

    # Depois processa linha a linha
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
            fragmento = linha
            i += 1
        else:
            i += 1

    return adicionadas, erros, fragmento

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text(
        "\U0001f916 SuKo-9000 BLACK EDITION\n\nSeleciona o que queres fazer:",
        reply_markup=menu_principal()
    )

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f916 Menu Principal", reply_markup=menu_principal())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "pool":
        pool = get_pool()
        if not pool:
            texto = "\U0001f4cb Pool vazia.\n\nManda direto: email:senha:Nome"
        else:
            texto = f"\U0001f4cb Pool ({len(pool)} pendentes):\n\n"
            for i, c in enumerate(pool, 1):
                texto += f"{i}. {c['email']} | {c.get('nome','?')}\n"
        await query.edit_message_text(texto, reply_markup=menu_principal())

    elif data == "add":
        await query.edit_message_text(
            "\u2795 Adicionar conta\n\n"
            "Manda no formato:\n"
            "email:senha:Nome Completo\n\n"
            "Pode mandar varias de uma vez, uma por linha.\n"
            "A data de nascimento e gerada automaticamente.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f3e0 Menu", callback_data="pool")]])
        )

    elif data == "clear":
        clear_pool()
        fragmento_buffer.clear()
        await query.edit_message_text("\U0001f5d1\ufe0f Pool limpa!", reply_markup=menu_principal())

    elif data == "status":
        pool = get_pool()
        active = get_active_job()
        waiting = is_waiting_code(chat_id)
        texto = (
            f"\U0001f4ca Status:\n\n"
            f"Contas pendentes: {len(pool)}\n"
            f"Job ativo: {'sim' if active else 'nao'}\n"
            f"Aguardando codigo: {'sim' if waiting else 'nao'}"
        )
        await query.edit_message_text(texto, reply_markup=menu_principal())

    elif data == "start_job":
        pool = get_pool()
        if not pool:
            await query.edit_message_text("\u26a0\ufe0f Pool vazia!", reply_markup=menu_principal())
            return
        if get_active_job():
            await query.edit_message_text("\u26a0\ufe0f Ja tem um job rodando!", reply_markup=menu_principal())
            return
        create_job(chat_id)
        await query.edit_message_text(
            f"\U0001f680 Job criado! {len(pool)} conta(s) na fila.\n\nRode no PC: python worker.py",
            reply_markup=menu_principal()
        )

    elif data == "resultados":
        rows = get_resultados()
        if not rows:
            texto = "\U0001f4c8 Nenhum resultado ainda."
        else:
            texto = "\U0001f4c8 Ultimos Resultados:\n\n"
            for r in rows:
                emoji = "\u2705" if r["status"] == "SUCESSO" else ("\u26a0\ufe0f" if r["status"] == "VERIFICAR" else "\u274c")
                texto += f"{emoji} {r['email']} -> {r['status']}\n"
        await query.edit_message_text(texto, reply_markup=menu_principal())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    logger.info(f"[MSG] chat_id={chat_id} | texto={repr(text)}")

    # Codigo de verificacao (so numeros, sem @)
    if is_waiting_code(chat_id) and "@" not in text and text.isdigit():
        save_codigo(chat_id, text)
        await update.message.reply_text("\u2705 Codigo salvo! O worker vai pegar automaticamente.")
        return

    tem_fragmento = chat_id in fragmento_buffer
    if "@" in text or tem_fragmento:
        if tem_fragmento:
            texto_completo = fragmento_buffer.pop(chat_id) + text
            logger.info(f"[FRAGMENTO] Juntando: {repr(texto_completo)}")
        else:
            texto_completo = text

        adicionadas, erros, fragmento = processar_texto(texto_completo)

        if fragmento:
            fragmento_buffer[chat_id] = fragmento
            logger.info(f"[FRAGMENTO] Guardando: {repr(fragmento)}")

        if adicionadas:
            resposta = f"\u2705 {len(adicionadas)} conta(s) adicionada(s):\n" + "\n".join(adicionadas)
            if fragmento:
                resposta += "\n\n\u23f3 Aguardando continuacao da ultima conta..."
            await update.message.reply_text(
                resposta,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("\U0001f4cb Ver Pool", callback_data="pool"),
                    InlineKeyboardButton("\U0001f680 Iniciar Job", callback_data="start_job")
                ]])
            )
            return
        elif fragmento:
            return
        else:
            await update.message.reply_text(
                f"\u274c Nao consegui processar. Formato esperado:\n`email:senha:Nome Completo`\n\nRecebido: {repr(text[:80])}"
            )
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
            logger.info("\U0001f916 SuKo-9000 rodando!")
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

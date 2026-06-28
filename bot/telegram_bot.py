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

def gerar_nascimento():
    ano = datetime.date.today().year - 22
    mes = random.randint(1, 12)
    max_dia = [31,28,31,30,31,30,31,31,30,31,30,31][mes-1]
    dia = random.randint(1, max_dia)
    return f"{dia:02d}/{mes:02d}/{ano}"

def parse_linha(linha):
    """
    Tenta extrair (email, senha, nome) de uma linha.
    Aceita:
      - email:senha:nome
      - email senha nome  (separado por espaço, se email vier primeiro)
    Retorna (email, senha, nome) ou None se não conseguir.
    """
    linha = linha.strip()
    if not linha or "@" not in linha:
        return None

    # Tenta separar por : primeiro
    # Divide só nas 2 primeiras ocorrências de :
    partes = linha.split(":", 2)
    if len(partes) == 3:
        email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
        if "@" in email and senha and nome:
            return email, senha, nome

    # Tenta separar por espaço: email senha resto_é_nome
    partes = linha.split(" ", 2)
    if len(partes) >= 3:
        email, senha, nome = partes[0].strip(), partes[1].strip(), partes[2].strip()
        if "@" in email and senha and nome:
            return email, senha, nome

    # Tem email e senha mas sem nome — gera nome genérico
    if len(partes) == 2:
        email, senha = partes[0].strip(), partes[1].strip()
        if "@" in email and senha:
            return email, senha, "Usuario"

    return None

def processar_texto(text):
    """
    Junta todas as linhas do texto e tenta montar contas.
    Lida com mensagens quebradas pelo Telegram.
    Retorna (adicionadas, erros).
    """
    adicionadas = []
    erros = []

    # Tenta processar linha por linha primeiro
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    processadas = set()

    for i, linha in enumerate(linhas):
        resultado = parse_linha(linha)
        if resultado:
            email, senha, nome = resultado
            nascimento = gerar_nascimento()
            add_to_pool(email, senha, nome, nascimento)
            adicionadas.append(f"{email} | {nome}")
            processadas.add(i)

    # Linhas não processadas que tenham @ podem ser fragmentos — tenta juntar com próxima
    sobras = [linhas[i] for i in range(len(linhas)) if i not in processadas]
    if sobras:
        # Tenta juntar tudo numa linha só e reprocessar
        junto = " ".join(sobras)
        resultado = parse_linha(junto)
        if resultado:
            email, senha, nome = resultado
            nascimento = gerar_nascimento()
            add_to_pool(email, senha, nome, nascimento)
            adicionadas.append(f"{email} | {nome}")
        elif sobras:
            for s in sobras:
                if "@" in s:
                    erros.append(f"Não consegui processar: {s[:50]}")

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
            "Exemplos:\n"
            "teste@gmail.com:Senha123:Joao Silva\n"
            "outro@gmail.com:Pass456!?:Tony\n\n"
            "Pode mandar várias de uma vez, uma por linha.\n"
            "A data de nascimento é gerada automaticamente.",
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

    print(f"[MSG] chat_id={chat_id} | texto={repr(text)}")

    # Código de verificação tem prioridade (só se não tiver @ na msg)
    if is_waiting_code(chat_id) and "@" not in text:
        save_codigo(chat_id, text.strip())
        await update.message.reply_text("✅ Codigo salvo! O worker vai pegar automaticamente.")
        return

    # Se tiver @ na mensagem, tenta processar como conta
    if "@" in text:
        adicionadas, erros = processar_texto(text)

        if adicionadas:
            resposta = f"✅ {len(adicionadas)} conta(s) adicionada(s):\n" + "\n".join(adicionadas)
            if erros:
                resposta += "\n\n❌ Erros:\n" + "\n".join(erros)
            await update.message.reply_text(
                resposta,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Ver Pool", callback_data="pool"),
                    InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")
                ]])
            )
            return
        elif erros:
            await update.message.reply_text("❌ Nao consegui processar:\n" + "\n".join(erros))
            return

    # Fallback
    await update.message.reply_text("Usa os botoes abaixo:", reply_markup=menu_principal())

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

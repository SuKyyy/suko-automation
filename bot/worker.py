import os
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_active_job():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE status IN ('running', 'waiting_code') ORDER BY criado_em DESC LIMIT 1")
            return cur.fetchone()

def get_pool():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pool WHERE status = 'pending' ORDER BY criado_em")
            return cur.fetchall()

def update_pool_status(email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE pool SET status = %s WHERE email = %s", (status, email))
        conn.commit()

def finish_job(job_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET status = 'done' WHERE id = %s", (job_id,))
        conn.commit()

def log_resultado(email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO resultados (email, status) VALUES (%s, %s)", (email, status))
        conn.commit()

def set_waiting_code(chat_id, waiting):
    with get_conn() as conn:
        with conn.cursor() as cur:
            status = 'waiting_code' if waiting else 'running'
            cur.execute(
                "UPDATE jobs SET status = %s WHERE chat_id = %s AND status IN ('running', 'waiting_code')",
                (status, chat_id)
            )
        conn.commit()

def get_codigo(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM codigos WHERE chat_id = %s AND usado = FALSE ORDER BY criado_em DESC LIMIT 1",
                (chat_id,)
            )
            return cur.fetchone()

def mark_codigo_usado(codigo_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE codigos SET usado = TRUE WHERE id = %s", (codigo_id,))
        conn.commit()

def send_message(chat_id, text):
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
    print(f"⏳ Aguardando código pelo Telegram...")
    start = time.time()
    while time.time() - start < timeout:
        row = get_codigo(chat_id)
        if row:
            mark_codigo_usado(row["id"])
            return row["codigo"]
        time.sleep(3)
    return None

def run_job(job):
    from cloakbrowser import launch

    chat_id = job["chat_id"]
    job_id = job["id"]
    pool = get_pool()

    if not pool:
        send_message(chat_id, "❌ Pool vazia!")
        finish_job(job_id)
        return

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

            # Clicar em cadastrar
            if not safe_click(page, "Cadastre-se gratuitamente"):
                safe_click(page, "Sign up for free")
            human_delay(2, 4)

            # Preencher email
            for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
                if safe_fill(page, sel, email):
                    break
            page.keyboard.press("Enter")
            human_delay(2, 3)

            # Clicar em "Continuar com uma senha"
            if not safe_click(page, "Continuar com uma senha"):
                safe_click(page, "Continue with a password")
            human_delay(1.5, 3)

            # Preencher senha
            for sel in ["input[type='password']", "input[name='password']"]:
                if safe_fill(page, sel, senha):
                    break
            page.keyboard.press("Enter")
            human_delay(2, 4)

            # Pedir código pelo Telegram
            set_waiting_code(chat_id, True)
            send_message(
                chat_id,
                f"📩 Conta `{email}` precisa do código de verificação.\n\nManda *só o código de 6 dígitos*."
            )

            code = wait_for_code(chat_id, timeout=300)
            set_waiting_code(chat_id, False)

            if not code:
                send_message(chat_id, f"⏰ Timeout esperando código. Pulando `{email}`.")
                log_resultado(email, "TIMEOUT_CODIGO")
                update_pool_status(email, "timeout")
                page.close()
                continue

            # Preencher o código
            preencheu = False
            for sel in [
                "input[placeholder*='dígito' i]",
                "input[placeholder*='código' i]",
                "input[placeholder*='code' i]",
                "input[name*='code' i]",
                "input[type='text']",
                "input[inputmode='numeric']"
            ]:
                try:
                    page.wait_for_selector(sel, timeout=3000)
                    page.fill(sel, code)
                    preencheu = True
                    break
                except:
                    continue

            if not preencheu:
                page.keyboard.type(code)

            page.keyboard.press("Enter")
            send_message(chat_id, "✅ Código colado! Verificando...")
            human_delay(3, 5)

            # Checa se entrou
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
            log_resultado(email, "ERRO")
            update_pool_status(email, "erro")
        finally:
            page.close()
            human_delay(5, 8)

    browser.close()
    finish_job(job_id)
    send_message(chat_id, "🏁 Job finalizado! Use /resultados pra ver.")
    print("✅ Job finalizado!")

def main():
    print("🖥️ Worker iniciado — aguardando jobs do Telegram...")
    print("   (deixa essa janela aberta, roda automaticamente quando clicar em Iniciar Job)\n")
    while True:
        try:
            job = get_active_job()
            if job and job["status"] == "running":
                print(f"📋 Job encontrado! ID: {job['id']}")
                run_job(job)
            else:
                print("⏳ Sem jobs. Checando de novo em 5s...", end="\r")
        except Exception as e:
            print(f"❌ Erro no loop: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()

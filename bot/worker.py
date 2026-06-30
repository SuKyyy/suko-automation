import os
import time
import random
import datetime
import signal
import sys
import traceback
import re
import requests
from dotenv import load_dotenv
import concurrent.futures

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

import psycopg2
from psycopg2.extras import RealDictCursor

# ==================== IMPORTS ====================
from bot.gpt.creator import criar_conta
from bot.gpt.automation import (
    human_delay,
    click_cadastro,
    safe_fill,
    safe_click_text,
    click_concluir,
    preencher_nome_idade,
    get_code_from_site,
    send_discord_webhook
)

# Import do Spotify (vamos criar depois)
try:
    from bot.spotify.creator import criar_conta_spotify
except ImportError:
    criar_conta_spotify = None

shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    print("\n\n[Ctrl+C] Sinal de encerramento recebido...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def cancel_all_running_jobs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET status='cancelado' WHERE status IN ('running', 'waiting_code')")
        conn.commit()
    print("[Shutdown] Jobs ativos foram cancelados no banco.")

def get_active_job():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE status='running' ORDER BY criado_em ASC LIMIT 1")
            return cur.fetchone()

def get_pool(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pool WHERE user_id=%s AND status='pending' ORDER BY criado_em", (user_id,))
            return cur.fetchall()

def update_pool_status(user_id, email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE pool SET status=%s WHERE user_id=%s AND email=%s", (status, user_id, email))
        conn.commit()
    print(f"[DB] Pool atualizado: {email} -> {status}")

def finish_job(job_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET status='done' WHERE id=%s", (job_id,))
        conn.commit()

def is_job_cancelled(job_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM jobs WHERE id=%s", (job_id,))
            row = cur.fetchone()
            return row and row['status'] == 'cancelado'

def log_resultado(user_id, email, status):
    if user_id is None:
        print("[ERRO] user_id is None no log_resultado - pulando")
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO resultados (user_id, email, status) VALUES (%s, %s, %s)", (user_id, email, status))
        conn.commit()

def set_waiting_code(chat_id, waiting):
    with get_conn() as conn:
        with conn.cursor() as cur:
            status = 'waiting_code' if waiting else 'running'
            cur.execute(
                "UPDATE jobs SET status=%s WHERE chat_id=%s AND status IN ('running','waiting_code')",
                (status, chat_id)
            )
        conn.commit()

def get_codigo(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM codigos WHERE chat_id=%s AND usado=FALSE ORDER BY criado_em DESC LIMIT 1",
                (chat_id,)
            )
            return cur.fetchone()

def mark_codigo_usado(codigo_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE codigos SET usado=TRUE WHERE id=%s", (codigo_id,))
        conn.commit()

def get_preco():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM configuracoes WHERE chave='preco_por_conta'")
            row = cur.fetchone()
            return float(row['valor']) if row else 1.0

def ajustar_saldo(chat_id, valor):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET saldo = saldo + %s WHERE chat_id=%s",
                (valor, chat_id)
            )
        conn.commit()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if r.status_code == 200:
            return r.json()['result']['message_id']
        return None
    except:
        return None

def edit_message(chat_id, message_id, text):
    if not message_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
    except:
        pass

def wait_for_code_manual(chat_id, job_id, timeout=120):
    print("Aguardando codigo pelo Telegram (manual)...")
    start = time.time()
    while time.time() - start < timeout:
        if is_job_cancelled(job_id) or shutdown_flag:
            print("Job cancelado durante espera de codigo.")
            return None
        row = get_codigo(chat_id)
        if row:
            mark_codigo_usado(row['id'])
            return row['codigo']
        time.sleep(3)
    return None

def run_job(job):
    from cloakbrowser import launch

    chat_id = job['chat_id']
    user_id = job['user_id']
    job_id = job['id']
    service = job.get('service', 'gpt')   # padrão gpt
    preco = get_preco()
    pool = get_pool(user_id)

    if not pool:
        send_message(chat_id, "Pool vazia!")
        finish_job(job_id)
        return

    total = len(pool)
    send_message(chat_id, f"Job iniciado! Processando {total} conta(s) de {service.upper()}...")

    browser = launch(headless=False, humanize=True)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []

            for conta in pool:
                if is_job_cancelled(job_id) or shutdown_flag:
                    break

                if service == 'spotify' and criar_conta_spotify:
                    future = executor.submit(
                        criar_conta_spotify,
                        browser,
                        conta,
                        chat_id,
                        user_id,
                        job_id,
                        preco,
                        send_message,
                        edit_message,
                        log_resultado,
                        update_pool_status,
                        ajustar_saldo,
                        wait_for_code_manual,
                        send_discord_webhook
                    )
                else:
                    future = executor.submit(
                        criar_conta,
                        browser,
                        conta,
                        chat_id,
                        user_id,
                        job_id,
                        preco,
                        send_message,
                        edit_message,
                        log_resultado,
                        update_pool_status,
                        ajustar_saldo,
                        wait_for_code_manual,
                        send_discord_webhook
                    )

                futures.append(future)

            concurrent.futures.wait(futures)

    finally:
        try:
            browser.close()
        except:
            pass
        finish_job(job_id)
        send_message(chat_id, "Job finalizado! Use /start pra ver os resultados.")
        print("Job finalizado!")


def main():
    print("Worker iniciado - aguardando jobs...\n")
    global shutdown_flag
    try:
        while not shutdown_flag:
            try:
                job = get_active_job()
                if job:
                    print(f"Job encontrado! ID: {job['id']} | user: {job['user_id']} | service: {job.get('service', 'gpt')}")
                    run_job(job)
                else:
                    if not shutdown_flag:
                        print("Sem jobs. Checando em 5s...", end="\r")
            except Exception as e:
                print(f"Erro no loop: {e}")
                traceback.print_exc()
            if not shutdown_flag:
                time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[Shutdown] Encerrando worker de forma segura...")
        cancel_all_running_jobs()
        print("Worker finalizado com segurança.")
        sys.exit(0)


if __name__ == "__main__":
    main()

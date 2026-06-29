import os
import time
import random
import datetime
import signal
import sys
import traceback
import re
import imaplib
import email
from email.header import decode_header
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# IMAP Gmail Catchall
IMAP_GMAIL_HOST = os.environ.get("IMAP_GMAIL_HOST", "imap.titan.email")
IMAP_GMAIL_PORT = int(os.environ.get("IMAP_GMAIL_PORT", 993))
IMAP_GMAIL_USER = os.environ.get("IMAP_GMAIL_USER")
IMAP_GMAIL_PASSWORD = os.environ.get("IMAP_GMAIL_PASSWORD")

# IMAP Outlook/Hotmail Catchall
IMAP_OUTLOOK_HOST = os.environ.get("IMAP_OUTLOOK_HOST", "imap.titan.email")
IMAP_OUTLOOK_PORT = int(os.environ.get("IMAP_OUTLOOK_PORT", 993))
IMAP_OUTLOOK_USER = os.environ.get("IMAP_OUTLOOK_USER")
IMAP_OUTLOOK_PASSWORD = os.environ.get("IMAP_OUTLOOK_PASSWORD")

import psycopg2
from psycopg2.extras import RealDictCursor

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

def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def click_cadastro(page):
    selectors = [
        "a[href*='signup']",
        "a[href*='register']",
        "button:has-text('Sign up')",
        "button:has-text('Cadastre-se')",
        "a:has-text('Sign up')",
        "a:has-text('Cadastre-se')",
        "button:has-text('Get started')",
        "a:has-text('Get started')",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=6000)
            el.scroll_into_view_if_needed()
            el.click()
            return True
        except:
            continue

    textos = ["Sign up", "Cadastre-se", "Get started", "Sign up for free", "Cadastre-se gratuitamente"]
    for texto in textos:
        try:
            page.get_by_text(texto, exact=False).first.click(timeout=5000)
            return True
        except:
            continue
    return False

def safe_fill(page, selector, value, timeout=8000):
    try:
        page.locator(selector).first.fill(value, timeout=timeout)
        return True
    except:
        try:
            page.fill(selector, value, timeout=timeout)
            return True
        except:
            return False

def safe_click_text(page, *textos, timeout=8000):
    for texto in textos:
        try:
            page.locator(f"button:has-text('{texto}')").first.click(timeout=timeout)
            return True
        except:
            pass
    for texto in textos:
        try:
            page.get_by_text(texto, exact=True).first.click(timeout=timeout)
            return True
        except:
            pass
    return False

def click_concluir(page):
    try:
        btn = page.locator("button:has-text('Concluir a criação da conta')").first
        btn.wait_for(timeout=6000)
        btn.scroll_into_view_if_needed()
        btn.click()
        return True
    except:
        pass
    for texto in ["Concluir", "Continue", "Submit", "Finish"]:
        try:
            btn = page.locator(f"button:has-text('{texto}')").first
            btn.wait_for(timeout=4000)
            btn.scroll_into_view_if_needed()
            btn.click()
            return True
        except:
            pass
    try:
        btns = page.locator("button[type='submit'], button[type='button']").all()
        for btn in btns:
            try:
                txt = btn.inner_text()
                if any(p in txt.lower() for p in ["conclu", "continu", "submit", "finish"]):
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    return True
            except:
                continue
    except:
        pass
    return False

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

def get_verification_code(target_email, start_time):
    """
    Busca o código de verificação no IMAP checando a cada 5 segundos.
    - Procura o email exato (com alias)
    - Só considera emails depois de start_time
    - Suporta dois catchalls
    """
    domain = target_email.split("@")[-1].lower()

    if "gmail.com" in domain:
        host = IMAP_GMAIL_HOST
        port = IMAP_GMAIL_PORT
        user = IMAP_GMAIL_USER
        password = IMAP_GMAIL_PASSWORD
    else:
        host = IMAP_OUTLOOK_HOST
        port = IMAP_OUTLOOK_PORT
        user = IMAP_OUTLOOK_USER
        password = IMAP_OUTLOOK_PASSWORD

    if not user or not password:
        print("[IMAP] Credenciais não configuradas no .env")
        return None

    print(f"[IMAP] Iniciando busca para {target_email} (a cada 5s)...")

    deadline = time.time() + 120  # 2 minutos

    while time.time() < deadline:
        if shutdown_flag:
            return None

        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select("INBOX")

            status, messages = mail.search(None, "ALL")
            email_ids = messages[0].split()[-50:]

            for eid in reversed(email_ids):
                status, msg_data = mail.fetch(eid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Horário do email
                date_tuple = email.utils.parsedate_tz(msg.get("Date"))
                if date_tuple:
                    email_time = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    if email_time < start_time:
                        continue  # email muito antigo

                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode(errors="ignore")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                from_addr = msg.get("From", "")

                # Verifica se é do ChatGPT e contém o email exato
                if ("ChatGPT" in from_addr or "openai.com" in from_addr.lower() or "tm.openai.com" in from_addr.lower()):
                    if target_email.lower() in body.lower():
                        match = re.search(r"\b(\d{6})\b", body)
                        if match:
                            code = match.group(1)
                            print(f"[IMAP] Código encontrado: {code}")
                            mail.close()
                            mail.logout()
                            return code

            mail.close()
            mail.logout()

        except Exception as e:
            print(f"[IMAP] Erro: {e}")

        print("[IMAP] Não encontrado ainda... esperando 5s")
        time.sleep(5)

    print("[IMAP] Timeout após 2 minutos")
    return None

def preencher_nome_idade(page, nome, nascimento):
    for sel in ["input[name='name']", "input[placeholder*='nome' i]", "input[placeholder*='name' i]"]:
        if safe_fill(page, sel, nome):
            break
    human_delay(0.5, 1)

    preencheu = False
    for _ in range(5):
        for sel in ["input[placeholder='Idade']", "input[placeholder*='idade' i]", "input[placeholder*='age' i]", 
                    "input[type='number']", "input[placeholder*='nascimento' i]", "input[placeholder*='data' i]", "input[type='date']"]:
            val = nascimento if 'data' in sel.lower() or 'nasc' in sel.lower() else str(calcular_idade(nascimento))
            if safe_fill(page, sel, val):
                preencheu = True
                break
        if preencheu:
            break
        human_delay(0.8, 1.5)

    if not preencheu:
        try:
            inputs = page.locator("input[type='text'], input[type='number']").all()
            if len(inputs) >= 2:
                inputs[1].fill(str(calcular_idade(nascimento)))
        except:
            pass

    human_delay(0.5, 1)
    click_concluir(page)
    human_delay(2, 4)

def calcular_idade(nascimento):
    try:
        partes = nascimento.split("/")
        if len(partes) == 3:
            dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            hoje = datetime.date.today()
            idade = hoje.year - ano - ((hoje.month, hoje.day) < (mes, dia))
            return str(idade)
    except:
        pass
    return "18"

def run_job(job):
    from cloakbrowser import launch

    chat_id = job['chat_id']
    user_id = job['user_id']
    job_id = job['id']
    preco = get_preco()
    pool = get_pool(user_id)

    if not pool:
        send_message(chat_id, "Pool vazia!")
        finish_job(job_id)
        return

    total = len(pool)
    send_message(chat_id, f"Job iniciado! Processando {total} conta(s)...")
    browser = launch(headless=False, humanize=True)

    try:
        for i, conta in enumerate(pool, 1):
            if is_job_cancelled(job_id) or shutdown_flag:
                send_message(chat_id, "Job cancelado.")
                break

            email = conta['email']
            senha = conta['senha']
            nome = conta.get('nome', '')
            nascimento = conta.get('nascimento', '')

            print(f"\n=== Criando: {email} ===")

            progress = f"""\ud83d\udccc {email}

Estado: Iniciando cadastro...
Progresso: [          ] 0%"""
            msg_id = send_message(chat_id, progress)

            page = browser.new_page()
            try:
                page.goto("https://chatgpt.com")
                page.wait_for_load_state("networkidle")
                human_delay(2, 4)

                if not click_cadastro(page):
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Falha ao encontrar botão de cadastro.")
                    log_resultado(user_id, email, "ERRO_CADASTRO")
                    update_pool_status(user_id, email, "erro")
                    page.close()
                    continue

                edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando email...\nProgresso: [\u2588\u2588        ] 20%")
                human_delay(1, 2)

                for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
                    if safe_fill(page, sel, email): break
                page.keyboard.press("Enter")
                human_delay(2, 3)

                edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando senha...\nProgresso: [\u2588\u2588\u2588\u2588    ] 40%")
                safe_click_text(page, "Continuar com uma senha", "Continue with a password")
                human_delay(1.5, 3)

                for sel in ["input[type='password']", "input[name='password']"]:
                    if safe_fill(page, sel, senha): break
                page.keyboard.press("Enter")
                human_delay(4, 6)

                ajustar_saldo(chat_id, -preco)
                human_delay(3, 5)

                # === LÓGICA IMAP COM POLLING ===
                start_time = datetime.datetime.now()
                code = get_verification_code(email, start_time)

                if code:
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Código encontrado via IMAP \u2705")
                    # preencher código
                    for sel in ["input[placeholder*='digito' i]", "input[placeholder*='codigo' i]", "input[type='text']"]:
                        try:
                            page.wait_for_selector(sel, timeout=3000)
                            page.fill(sel, code)
                            break
                        except:
                            continue
                    page.keyboard.press("Enter")
                    human_delay(4, 6)
                    preencher_nome_idade(page, nome, nascimento)
                else:
                    # fallback manual
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Aguardando código no Telegram...")
                    send_message(chat_id, f"{email}\nManda o código de 6 dígitos:")
                    code = wait_for_code_manual(chat_id, job_id, timeout=120)
                    if not code:
                        edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Timeout. Reembolsando...")
                        ajustar_saldo(chat_id, preco)
                        log_resultado(user_id, email, "TIMEOUT")
                        update_pool_status(user_id, email, "timeout")
                        page.close()
                        continue

                    for sel in ["input[placeholder*='digito' i]", "input[placeholder*='codigo' i]", "input[type='text']"]:
                        try:
                            page.wait_for_selector(sel, timeout=3000)
                            page.fill(sel, code)
                            break
                        except:
                            continue
                    page.keyboard.press("Enter")
                    human_delay(4, 6)
                    preencher_nome_idade(page, nome, nascimento)

                human_delay(2, 4)

                try:
                    page.wait_for_selector("text=ChatGPT", timeout=10000)
                    edit_message(chat_id, msg_id, f"""\ud83d\udccc {email}

\u2705 CONTA CRIADA COM SUCESSO!

Email: `{email}`
Copie e cole: https://tempmailsuko.shop/en/infinity""")
                    log_resultado(user_id, email, "SUCESSO")
                    update_pool_status(user_id, email, "done")
                except:
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u26a0️ Pode precisar de verificação manual.\n\nEmail: `{email}`")
                    log_resultado(user_id, email, "VERIFICAR")
                    update_pool_status(user_id, email, "verificar")
                    ajustar_saldo(chat_id, preco)

            except Exception as e:
                print("\n=== ERRO DETALHADO ===")
                traceback.print_exc()
                edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Erro: {str(e)[:100]}")
                log_resultado(user_id, email, "ERRO")
                update_pool_status(user_id, email, "erro")
                ajustar_saldo(chat_id, preco)
            finally:
                try:
                    page.close()
                except:
                    pass
                human_delay(5, 8)

            if shutdown_flag:
                break
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
                    print(f"Job encontrado! ID: {job['id']} | user: {job['user_id']}")
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

import os
import time
import random
import datetime
import signal
import sys
import traceback
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

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

def create_progress_bar(percent):
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent}%"

def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def click_cadastro(page):
    # Tenta vários seletores comuns do ChatGPT atual
    selectors = [
        "a[href*='signup']",
        "a[href*='register']",
        "button:has-text('Sign up')",
        "button:has-text('Cadastre-se')",
        "a:has-text('Sign up')",
        "a:has-text('Cadastre-se')",
        "button:has-text('Get started')",
        "a:has-text('Get started')",
        "button:has-text('Sign up for free')",
        "a:has-text('Sign up for free')",
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

    # Fallback mais amplo por texto
    textos = [
        "Sign up", "Cadastre-se", "Get started", "Sign up for free",
        "Cadastre-se gratuitamente", "Create account", "Criar conta"
    ]
    for texto in textos:
        try:
            page.get_by_text(texto, exact=False).first.click(timeout=5000)
            return True
        except:
            continue

    # Último recurso: tenta qualquer botão que pareça de cadastro
    try:
        btns = page.locator("button, a[role='button']").all()
        for btn in btns:
            try:
                txt = btn.inner_text()
                if any(p in txt.lower() for p in ["sign up", "cadastre", "get started", "create account"]):
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    return True
            except:
                continue
    except:
        pass

    return False

def safe_fill(page, selector, value, timeout=8000):
    try:
        page.locator(selector).first.fill(value, timeout=timeout)
        return True
    except:
        try:
            page.fill(selector, value, timeout=timeout)
            return True
        except: return False

def safe_click_text(page, *textos, timeout=8000):
    for texto in textos:
        try:
            page.locator(f"button:has-text('{texto}')").first.click(timeout=timeout)
            return True
        except: pass
    for texto in textos:
        try:
            page.get_by_text(texto, exact=True).first.click(timeout=timeout)
            return True
        except: pass
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

def wait_for_code(chat_id, job_id, timeout=120):
    print("Aguardando codigo pelo Telegram...")
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

def preencher_nome_idade(page, nome, nascimento):
    for sel in ["input[name='name']", "input[placeholder*='nome' i]", "input[placeholder*='name' i]", "input[type='text']"]:
        if safe_fill(page, sel, nome): break
    human_delay(0.5, 1)

    preencheu = False
    for _ in range(4):
        try:
            el = page.locator("input[placeholder*='nascimento' i], input[placeholder*='data de nascimento' i], input[placeholder*='birth' i], input[type='date']").first
            el.wait_for(timeout=2000)
            el.fill(nascimento)
            preencheu = True
            break
        except:
            try:
                el = page.locator("input[type='date']").first
                el.wait_for(timeout=1500)
                partes = nascimento.split("/")
                if len(partes) == 3:
                    data_iso = f"{partes[2]}-{partes[1]}-{partes[0]}"
                    el.fill(data_iso)
                preencheu = True
                break
            except:
                pass

        try:
            idade = calcular_idade(nascimento)
            for sel in ["input[type='number']", "input[placeholder*='idade' i]", "input[placeholder*='age' i]", "input[name*='age' i]"]:
                if safe_fill(page, sel, idade):
                    preencheu = True
                    break
        except:
            pass

        human_delay(0.8, 1.5)

    if not preencheu:
        try:
            inputs = page.locator("input[type='text'], input[type='number']").all()
            if len(inputs) >= 2:
                inputs[1].fill(idade)
        except:
            pass

    human_delay(0.5, 1)
    click_concluir(page)
    human_delay(2, 4)

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
                human_delay(3, 5)

                ajustar_saldo(chat_id, -preco)

                human_delay(3, 5)

                nome_ok = False
                idade_ok = False

                try:
                    page.locator("input[name='name'], input[placeholder*='nome' i]").first.fill(nome, timeout=5000)
                    nome_ok = True
                    human_delay(0.6, 1.2)
                except:
                    pass

                if nome_ok:
                    for _ in range(4):
                        try:
                            el = page.locator("input[placeholder*='nascimento' i], input[placeholder*='data de nascimento' i], input[placeholder*='birth' i], input[type='date']").first
                            el.wait_for(timeout=2000)
                            el.fill(nascimento)
                            idade_ok = True
                            break
                        except:
                            try:
                                el = page.locator("input[type='date']").first
                                el.wait_for(timeout=1500)
                                partes = nascimento.split("/")
                                if len(partes) == 3:
                                    data_iso = f"{partes[2]}-{partes[1]}-{partes[0]}"
                                    el.fill(data_iso)
                                idade_ok = True
                                break
                            except:
                                pass

                        try:
                            idade = calcular_idade(nascimento)
                            for sel in ["input[type='number']", "input[placeholder*='idade' i]", "input[placeholder*='age' i]", "input[name*='age' i]"]:
                                if safe_fill(page, sel, idade):
                                    idade_ok = True
                                    break
                        except:
                            pass

                        human_delay(0.8, 1.5)

                if nome_ok and idade_ok:
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Pulou código \u2705\nProgresso: [\u2588\u2588\u2588\u2588\u2588\u2588    ] 70%")
                    click_concluir(page)
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

                else:
                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Aguardando código...\nProgresso: [\u2588\u2588\u2588\u2588    ] 50%")

                    send_message(chat_id, f"{email}\nManda o código de 6 dígitos:")

                    code = wait_for_code(chat_id, job_id, timeout=120)

                    if not code:
                        edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Timeout (2 min). Reembolsando...")
                        ajustar_saldo(chat_id, preco)
                        log_resultado(user_id, email, "TIMEOUT")
                        update_pool_status(user_id, email, "timeout")
                        page.close()
                        continue

                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando código...\nProgresso: [\u2588\u2588\u2588\u2588\u2588    ] 70%")

                    preencheu = False
                    for sel in ["input[placeholder*='digito' i]", "input[placeholder*='codigo' i]", "input[placeholder*='code' i]", "input[name*='code' i]", "input[inputmode='numeric']", "input[type='text']"]:
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
                    human_delay(3, 5)

                    edit_message(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Preenchendo nome e idade...\nProgresso: [\u2588\u2588\u2588\u2588\u2588\u2588    ] 80%")

                    try:
                        page.locator("input[name='name'], input[placeholder*='nome' i]").first.fill(nome, timeout=4000)
                        human_delay(0.5, 1)
                        try:
                            el = page.locator("input[placeholder*='nascimento' i], input[placeholder*='data' i], input[type='date']").first
                            el.fill(nascimento, timeout=3000)
                        except:
                            idade = calcular_idade(nascimento)
                            page.locator("input[type='number'], input[placeholder*='idade' i]").first.fill(idade, timeout=2500)
                    except:
                        pass

                    click_concluir(page)
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

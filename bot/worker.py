import os
import time
import random
import datetime
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
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def calcular_idade(nascimento_str):
    hoje = datetime.date.today()
    partes = nascimento_str.strip().split("/")
    try:
        if len(partes) == 3:
            dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            nasc = datetime.date(ano, mes, dia)
            return str(hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day)))
        return str(hoje.year - int(partes[0]))
    except:
        return "22"

def create_progress_bar(percent):
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent}%"

def click_cadastro(page):
    for sel in ["a[href*='signup']", "a[href*='register']", "button:has-text('Cadastre')", "a:has-text('Cadastre')", "button:has-text('Sign up')", "a:has-text('Sign up')"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=5000)
            el.click()
            return True
        except: continue
    for texto in ["Cadastre-se gratuitamente", "Sign up for free", "Sign up", "Cadastre"]:
        try:
            page.get_by_text(texto, exact=False).first.click(timeout=5000)
            return True
        except: continue
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

def wait_for_code(chat_id, job_id, timeout=300):
    print("Aguardando codigo pelo Telegram...")
    start = time.time()
    while time.time() - start < timeout:
        if is_job_cancelled(job_id):
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
    try:
        el = page.locator("input[type='date']").first
        el.wait_for(timeout=2000)
        partes = nascimento.split("/")
        data_iso = f"{partes[2]}-{partes[1]}-{partes[0]}" if len(partes) == 3 else nascimento
        el.fill(data_iso)
        preencheu = True
    except:
        pass

    if not preencheu:
        idade = calcular_idade(nascimento)
        for sel in ["input[type='number']", "input[placeholder*='idade' i]", "input[placeholder*='age' i]", "input[name*='age' i]"]:
            if safe_fill(page, sel, idade):
                preencheu = True
                break
    if not preencheu:
        idade = calcular_idade(nascimento)
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
    send_message(chat_id, f"🚀 Job iniciado! Processando {total} conta(s)...")
    browser = launch(headless=False, humanize=True)

    try:
        for i, conta in enumerate(pool, 1):
            if is_job_cancelled(job_id):
                send_message(chat_id, "Job cancelado pelo admin.")
                break

            percent = int((i / total) * 100)
            bar = create_progress_bar(percent)
            send_message(chat_id, f"📊 Progresso do Job\n{bar} ({i}/{total} contas)")

            email = conta['email']
            senha = conta['senha']
            nome = conta.get('nome', '')
            nascimento = conta.get('nascimento', '')

            print(f"\n=== Criando: {email} ===")
            send_message(chat_id, f"Iniciando: `{email}`")

            page = browser.new_page()
            try:
                page.goto("https://chatgpt.com")
                page.wait_for_load_state("networkidle")
                human_delay(2, 4)

                if not click_cadastro(page):
                    send_message(chat_id, f"Nao achei botao de cadastro. Pulando `{email}`.")
                    log_resultado(user_id, email, "ERRO_CADASTRO")
                    update_pool_status(user_id, email, "erro")
                    page.close()
                    continue
                human_delay(2, 4)

                for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
                    if safe_fill(page, sel, email): break
                page.keyboard.press("Enter")
                human_delay(2, 3)

                safe_click_text(page, "Continuar com uma senha", "Continue with a password")
                human_delay(1.5, 3)

                for sel in ["input[type='password']", "input[name='password']"]:
                    if safe_fill(page, sel, senha): break
                page.keyboard.press("Enter")
                human_delay(2, 4)

                ajustar_saldo(chat_id, -preco)

                set_waiting_code(chat_id, True)
                send_message(chat_id, f"Conta `{email}` precisa do codigo de verificacao.\n\nManda so o codigo de 6 digitos.")

                code = wait_for_code(chat_id, job_id, timeout=300)
                set_waiting_code(chat_id, False)

                if not code:
                    send_message(chat_id, f"Timeout/cancelado. Reembolsando `{email}`.")
                    ajustar_saldo(chat_id, preco)
                    log_resultado(user_id, email, "TIMEOUT")
                    update_pool_status(user_id, email, "timeout")
                    page.close()
                    continue

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
                send_message(chat_id, "Codigo colado! Aguardando...")
                human_delay(3, 5)

                try:
                    page.wait_for_selector("text=Quantos anos", timeout=8000)
                    preencher_nome_idade(page, nome, nascimento)
                except:
                    try:
                        page.wait_for_selector("input[placeholder*='nome' i], input[placeholder*='name' i]", timeout=5000)
                        preencher_nome_idade(page, nome, nascimento)
                    except:
                        pass

                human_delay(2, 4)

                try:
                    page.wait_for_selector("text=ChatGPT", timeout=10000)
                    send_message(chat_id, f"Conta `{email}` criada com sucesso!")
                    log_resultado(user_id, email, "SUCESSO")
                    update_pool_status(user_id, email, "done")
                except:
                    send_message(chat_id, f"`{email}` pode precisar de verificacao manual.")
                    log_resultado(user_id, email, "VERIFICAR")
                    update_pool_status(user_id, email, "verificar")
                    ajustar_saldo(chat_id, preco)

            except Exception as e:
                send_message(chat_id, f"Erro em `{email}`: {str(e)[:80]}")
                log_resultado(user_id, email, "ERRO")
                update_pool_status(user_id, email, "erro")
                ajustar_saldo(chat_id, preco)
            finally:
                try:
                    page.close()
                except:
                    pass
                human_delay(5, 8)
    finally:
        try:
            browser.close()
        except:
            pass
        finish_job(job_id)
        send_message(chat_id, "✅ Job finalizado! Use /start pra ver os resultados.")
        print("Job finalizado!")

def main():
    print("Worker iniciado - aguardando jobs...\n")
    while True:
        try:
            job = get_active_job()
            if job:
                print(f"Job encontrado! ID: {job['id']} | user: {job['user_id']}")
                run_job(job)
            else:
                print("Sem jobs. Checando em 5s...", end="\r")
        except Exception as e:
            print(f"Erro no loop: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()

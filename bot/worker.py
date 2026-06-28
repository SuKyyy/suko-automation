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

def calcular_idade(nascimento_str):
    hoje = datetime.date.today()
    partes = nascimento_str.strip().split("/")
    try:
        if len(partes) == 3:
            dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            nascimento = datetime.date(ano, mes, dia)
            idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
        else:
            ano = int(partes[0])
            idade = hoje.year - ano
        return str(idade)
    except Exception as e:
        print(f"  Erro ao calcular idade de '{nascimento_str}': {e}")
        return "22"

def click_cadastro(page):
    seletores = [
        "a[href*='signup']",
        "a[href*='register']",
        "button:has-text('Cadastre')",
        "a:has-text('Cadastre')",
        "button:has-text('Sign up')",
        "a:has-text('Sign up')",
    ]
    for sel in seletores:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=5000)
            el.click()
            return True
        except:
            continue
    for texto in ["Cadastre-se gratuitamente", "Sign up for free", "Sign up", "Cadastre"]:
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
        except: return False

def safe_click_text(page, *textos, timeout=8000):
    """Clica em texto, priorizando buttons sobre links."""
    for texto in textos:
        # Tenta button primeiro (evita clicar em links como 'Termos de uso')
        try:
            page.locator(f"button:has-text('{texto}')").first.click(timeout=timeout)
            return True
        except: pass
    for texto in textos:
        # Fallback: qualquer elemento com o texto
        try:
            page.get_by_text(texto, exact=True).first.click(timeout=timeout)
            return True
        except: pass
    return False

def click_concluir(page):
    """Clica especificamente no botao de concluir, nunca em links."""
    textos = ["Concluir a cria\u00e7\u00e3o da conta", "Concluir", "Continue", "Submit", "Finish"]
    for texto in textos:
        try:
            btn = page.locator(f"button:has-text('{texto}')").first
            btn.wait_for(timeout=3000)
            btn.scroll_into_view_if_needed()
            btn.click()
            print(f"  Clicou em botao: {texto}")
            return True
        except: pass
    # Fallback: pega o unico button visivel na pagina
    try:
        btns = page.locator("button[type='submit'], button[type='button']").all()
        for btn in btns:
            txt = btn.inner_text()
            if any(p in txt.lower() for p in ["conclu", "continu", "submit", "finish"]):
                btn.scroll_into_view_if_needed()
                btn.click()
                print(f"  Clicou em botao fallback: {txt}")
                return True
    except: pass
    return False

def wait_for_code(chat_id, timeout=300):
    print("Aguardando codigo pelo Telegram...")
    start = time.time()
    while time.time() - start < timeout:
        row = get_codigo(chat_id)
        if row:
            mark_codigo_usado(row["id"])
            return row["codigo"]
        time.sleep(3)
    return None

def preencher_nome_idade(page, nome, nascimento):
    print(f"  Preenchendo nome: {nome} | nascimento: {nascimento}")

    for sel in ["input[name='name']", "input[placeholder*='nome' i]", "input[placeholder*='name' i]", "input[type='text']"]:
        if safe_fill(page, sel, nome):
            print(f"  Nome preenchido via {sel}")
            break
    human_delay(0.5, 1)

    preencheu_idade = False

    try:
        el = page.locator("input[type='date']").first
        el.wait_for(timeout=2000)
        partes = nascimento.split("/")
        data_iso = f"{partes[2]}-{partes[1]}-{partes[0]}" if len(partes) == 3 else nascimento
        el.fill(data_iso)
        preencheu_idade = True
        print(f"  Idade preenchida como date: {data_iso}")
    except:
        pass

    if not preencheu_idade:
        idade = calcular_idade(nascimento)
        for sel in [
            "input[type='number']",
            "input[placeholder*='idade' i]",
            "input[placeholder*='age' i]",
            "input[name*='age' i]",
        ]:
            if safe_fill(page, sel, idade):
                preencheu_idade = True
                print(f"  Idade preenchida via {sel}: {idade}")
                break

    if not preencheu_idade:
        idade = calcular_idade(nascimento)
        try:
            inputs = page.locator("input[type='text'], input[type='number']").all()
            if len(inputs) >= 2:
                inputs[1].fill(idade)
                preencheu_idade = True
                print(f"  Idade preenchida no segundo input: {idade}")
        except:
            pass

    human_delay(0.5, 1)
    click_concluir(page)  # usa funcao especifica que so clica em button
    human_delay(2, 4)

def run_job(job):
    from cloakbrowser import launch

    chat_id = job["chat_id"]
    job_id = job["id"]
    pool = get_pool()

    if not pool:
        send_message(chat_id, "Pool vazia!")
        finish_job(job_id)
        return

    send_message(chat_id, f"Worker conectado! Iniciando {len(pool)} conta(s)...")
    browser = launch(headless=False, humanize=True)

    try:
        for conta in pool:
            email = conta["email"]
            senha = conta["senha"]
            nome = conta.get("nome", "")
            nascimento = conta.get("nascimento", "")

            print(f"\n=== Criando: {email} ===")
            send_message(chat_id, f"Iniciando: `{email}`")

            page = browser.new_page()
            try:
                page.goto("https://chatgpt.com")
                page.wait_for_load_state("networkidle")
                human_delay(2, 4)

                if not click_cadastro(page):
                    send_message(chat_id, f"Nao achei o botao de cadastro em `{email}`. Pulando.")
                    log_resultado(email, "ERRO_CADASTRO")
                    update_pool_status(email, "erro")
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

                set_waiting_code(chat_id, True)
                send_message(chat_id, f"Conta `{email}` precisa do codigo de verificacao.\n\nManda so o codigo de 6 digitos.")

                code = wait_for_code(chat_id, timeout=300)
                set_waiting_code(chat_id, False)

                if not code:
                    send_message(chat_id, f"Timeout esperando codigo. Pulando `{email}`.")
                    log_resultado(email, "TIMEOUT_CODIGO")
                    update_pool_status(email, "timeout")
                    page.close()
                    continue

                preencheu = False
                for sel in [
                    "input[placeholder*='digito' i]",
                    "input[placeholder*='codigo' i]",
                    "input[placeholder*='code' i]",
                    "input[name*='code' i]",
                    "input[inputmode='numeric']",
                    "input[type='text']",
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
                send_message(chat_id, "Codigo colado! Aguardando proxima tela...")
                human_delay(3, 5)

                # Tela de nome e idade
                try:
                    page.wait_for_selector("text=Quantos anos", timeout=8000)
                    print("  Tela de nome/idade detectada!")
                    preencher_nome_idade(page, nome, nascimento)
                except:
                    try:
                        page.wait_for_selector("input[placeholder*='nome' i], input[placeholder*='name' i]", timeout=5000)
                        preencher_nome_idade(page, nome, nascimento)
                    except:
                        print("  Tela de nome/idade nao detectada, continuando...")

                human_delay(2, 4)

                try:
                    page.wait_for_selector("text=ChatGPT", timeout=10000)
                    send_message(chat_id, f"Conta `{email}` criada com sucesso!")
                    log_resultado(email, "SUCESSO")
                    update_pool_status(email, "done")
                except:
                    send_message(chat_id, f"`{email}` pode precisar de verificacao manual.")
                    log_resultado(email, "VERIFICAR")
                    update_pool_status(email, "verificar")

            except Exception as e:
                send_message(chat_id, f"Erro em `{email}`: {str(e)[:100]}")
                log_resultado(email, "ERRO")
                update_pool_status(email, "erro")
            finally:
                try: page.close()
                except: pass
                human_delay(5, 8)
    finally:
        try: browser.close()
        except: pass
        finish_job(job_id)
        send_message(chat_id, "Job finalizado! Use /resultados pra ver.")
        print("Job finalizado!")

def main():
    print("Worker iniciado - aguardando jobs do Telegram...")
    print("(deixa essa janela aberta)\n")
    while True:
        try:
            job = get_active_job()
            if job and job["status"] == "running":
                print(f"Job encontrado! ID: {job['id']}")
                run_job(job)
            else:
                print("Sem jobs. Checando de novo em 5s...", end="\r")
        except Exception as e:
            print(f"Erro no loop: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()

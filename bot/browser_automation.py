import time
import random
import re
import datetime
import requests
import traceback
from cloakbrowser import launch

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

def preencher_nome_idade(page, nome, nascimento):
    for sel in ["input[name='name']", "input[placeholder*='nome' i]", "input[placeholder*='name' i]"]:
        if safe_fill(page, sel, nome):
            break
    human_delay(0.8, 1.5)

    try:
        if page.locator("text=Data de nascimento").count() > 0:
            print("[IDADE] Campo de Data de nascimento detectado")
            date_input = None
            for sel in ["input[placeholder*='nasc' i]", "input[placeholder*='data' i]", "input[type='text']", "input"]:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible():
                        date_input = inp
                        break
                except:
                    continue
            if date_input:
                date_input.click()
                human_delay(0.5, 1)
                for _ in range(4):
                    page.keyboard.press("Backspace")
                    human_delay(0.1, 0.3)
                try:
                    ano = nascimento.split("/")[2]
                    page.keyboard.type(ano)
                    print(f"[IDADE] Ano corrigido para: {ano}")
                except:
                    page.keyboard.type(nascimento[-4:])
                human_delay(0.5, 1)
    except Exception as e:
        print(f"[IDADE] Erro ao tratar data de nascimento: {e}")

    try:
        for sel in ["input[placeholder='Idade']", "input[placeholder*='idade' i]", "input[placeholder*='age' i]", "input[type='number']"]:
            if safe_fill(page, sel, str(calcular_idade(nascimento))):
                print("[IDADE] Idade preenchida")
                break
    except:
        pass

    human_delay(0.8, 1.5)
    click_concluir(page)
    human_delay(2, 4)

    # ==================== NOVO: Clique no botão "Continuar" da tela "Tudo pronto" ====================
    try:
        for texto in ["Continuar", "Continue", "All set", "Tudo pronto"]:
            try:
                btn = page.get_by_text(texto, exact=False).first
                if btn.is_visible(timeout=5000):
                    btn.click()
                    print("[FINAL] ✅ Clicou em 'Continuar' na tela 'Tudo pronto'")
                    human_delay(2, 3)
                    break
            except:
                continue
    except Exception as e:
        print(f"[FINAL] Erro ao tentar clicar Continuar: {e}")


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

def get_code_from_site(browser, target_email):
    email_page = None
    try:
        email_page = browser.new_page()
        email_page.goto("https://tempmailsuko.shop/pt/infinity")
        human_delay(2, 3)

        # Preenche o email
        for sel in ["input[placeholder*='email' i]", "input[type='email']", "input[name='email']"]:
            try:
                email_page.fill(sel, target_email, timeout=8000)
                break
            except:
                continue

        human_delay(1, 2)
        email_page.keyboard.press("Enter")
        print("[SITE] Email enviado. Aguardando inbox...")

        # Espera a inbox carregar (aumentei o timeout)
        try:
            email_page.wait_for_selector("text=ChatGPT", timeout=60000)  # 60 segundos
            print("[SITE] Inbox carregou")
        except:
            print("[SITE] Timeout esperando inbox - tentando mesmo assim")

        human_delay(3, 5)

        # Tenta clicar no email várias vezes
        clicked = False
        for attempt in range(5):  # Tenta 5 vezes
            try:
                email_page.locator("text=ChatGPT").first.click(timeout=8000)
                print(f"[SITE] Clicou no email (tentativa {attempt + 1})")
                clicked = True
                break
            except:
                human_delay(2, 3)
                print(f"[SITE] Tentativa {attempt + 1} de clicar no email falhou")

        if not clicked:
            print("[SITE] Não conseguiu clicar no email")

        human_delay(3, 5)

        # Tenta extrair o código várias vezes
        for attempt in range(6):  # Tenta 6 vezes
            try:
                page_text = email_page.content()
                match = re.search(r"\b(\d{6})\b", page_text)
                if match:
                    code = match.group(1)
                    print(f"[SITE] ✅ Código encontrado: {code}")
                    email_page.close()
                    return code
                print(f"[SITE] Código ainda não apareceu (tentativa {attempt + 1})")
                human_delay(4, 6)
            except Exception as e:
                print(f"[SITE] Erro ao extrair código: {e}")
                human_delay(3, 5)

        print("[SITE] ❌ Não conseguiu pegar o código após várias tentativas")
        if email_page:
            email_page.close()
        return None

    except Exception as e:
        print(f"[SITE] Erro geral: {e}")
        if email_page:
            try:
                email_page.close()
            except:
                pass
        return None
def criar_conta(browser, conta, chat_id, user_id, job_id, preco, send_message_func, edit_message_func, log_resultado_func, update_pool_status_func, ajustar_saldo_func, wait_for_code_manual_func, send_discord_webhook_func):
    email = conta['email']
    senha = conta['senha']
    nome = conta.get('nome', '')
    nascimento = conta.get('nascimento', '')

    print(f"\n=== Criando (paralelo): {email} ===")

    progress = f"""\ud83d\udccc {email}

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
                edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Falha ao encontrar botão de cadastro.")
                log_resultado_func(user_id, email, "ERRO_CADASTRO")
                update_pool_status_func(user_id, email, "erro")
                page.close()
                local_browser.close()
                return

        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando email...")
        human_delay(1, 2)

        for sel in ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]:
            if safe_fill(page, sel, email): break
        page.keyboard.press("Enter")
        human_delay(2, 3)

        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando senha...")
        safe_click_text(page, "Continuar com uma senha", "Continue with a password")
        human_delay(1.5, 3)

        for sel in ["input[type='password']", "input[name='password']"]:
            if safe_fill(page, sel, senha): break
        page.keyboard.press("Enter")
        human_delay(4, 6)

        ajustar_saldo_func(chat_id, -preco)

        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Buscando código...")

        code = get_code_from_site(local_browser, email)

        if not code:
            edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Aguardando código no Telegram...")
            send_message_func(chat_id, f"{email}\nManda o código de 6 dígitos:")
            code = wait_for_code_manual_func(chat_id, job_id, timeout=120)

        if not code:
            edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Timeout. Reembolsando...")
            ajustar_saldo_func(chat_id, preco)
            log_resultado_func(user_id, email, "TIMEOUT")
            update_pool_status_func(user_id, email, "timeout")
            page.close()
            local_browser.close()
            return

        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Colocando código...")

        for sel in ["input[placeholder*='digito' i]", "input[placeholder*='codigo' i]", "input[type='text']"]:
            try:
                page.wait_for_selector(sel, timeout=3000)
                page.fill(sel, code)
                break
            except:
                continue

        page.keyboard.press("Enter")
        human_delay(4, 6)

        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\nEstado: Preenchendo nome e idade...")
        preencher_nome_idade(page, nome, nascimento)

        human_delay(2, 4)

        try:
            page.wait_for_selector("text=ChatGPT", timeout=10000)
            edit_message_func(chat_id, msg_id, f"""\ud83d\udccc {email}

\u2705 CONTA CRIADA COM SUCESSO! (paralelo)""")
            log_resultado_func(user_id, email, "SUCESSO")
            update_pool_status_func(user_id, email, "done")

            send_discord_webhook_func(email, senha)

        except:
            edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u26a0️ Pode precisar de verificação manual.\n\nEmail: `{email}`")
            log_resultado_func(user_id, email, "VERIFICAR")
            update_pool_status_func(user_id, email, "verificar")
            ajustar_saldo_func(chat_id, preco)

    except Exception as e:
        print("\n=== ERRO DETALHADO (paralelo) ===")
        traceback.print_exc()
        edit_message_func(chat_id, msg_id, f"\ud83d\udccc {email}\n\n\u274c Erro: {str(e)[:100]}")
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

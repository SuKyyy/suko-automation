import time
import random
import re

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

        for sel in ["input[placeholder*='email' i]", "input[type='email']", "input[name='email']"]:
            try:
                email_page.fill(sel, target_email, timeout=6000)
                break
            except:
                continue

        human_delay(1, 2)
        email_page.keyboard.press("Enter")
        print("[SITE] Email enviado. Aguardando inbox...")

        try:
            email_page.wait_for_selector("text=ChatGPT", timeout=45000)
            print("[SITE] Inbox carregou")
        except:
            print("[SITE] Timeout esperando inbox")

        human_delay(2, 3)

        try:
            email_page.locator("text=ChatGPT").first.click(timeout=8000)
            print("[SITE] Clicou no email")
            human_delay(2, 3)
        except Exception as e:
            print(f"[SITE] Erro ao clicar: {e}")

        try:
            human_delay(2, 4)
            page_text = email_page.content()
            match = re.search(r"\b(\d{6})\b", page_text)
            if match:
                code = match.group(1)
                print(f"[SITE] ✅ Código encontrado na página: {code}")
                email_page.close()
                return code
            print("[SITE] Nenhum código de 6 dígitos encontrado na página")
        except Exception as e:
            print(f"[SITE] Erro ao extrair código: {e}")

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
import time
import random
import os
import requests
from cloakbrowser import launch

def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def solve_recaptcha_2captcha(page, site_key, url):
    api_key = os.environ.get("TWOCAPTCHA_API_KEY")
    if not api_key:
        print("[SPOTIFY] TWOCAPTCHA_API_KEY não encontrada")
        return False

    print("[SPOTIFY] Enviando reCAPTCHA para 2Captcha...")

    try:
        resp = requests.post("http://2captcha.com/in.php", data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": url,
            "json": 1
        }, timeout=30).json()

        if resp.get("status") != 1:
            print(f"[SPOTIFY] Erro ao enviar: {resp}")
            return False

        captcha_id = resp["request"]
        print(f"[SPOTIFY] Captcha ID: {captcha_id} - Aguardando solução...")

        for _ in range(24):
            time.sleep(5)
            result = requests.get(
                f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1",
                timeout=10
            ).json()

            if result.get("status") == 1:
                token = result["request"]
                print("[SPOTIFY] ✅ reCAPTCHA resolvido!")
                page.evaluate(f"document.getElementById('g-recaptcha-response').innerHTML = '{token}';")
                human_delay(1, 2)
                return True

        print("[SPOTIFY] Timeout no 2Captcha")
        return False

    except Exception as e:
        print(f"[SPOTIFY] Erro no 2Captcha: {e}")
        return False


def criar_conta_spotify(browser, conta, chat_id, user_id, job_id, preco, send_message_func, edit_message_func, log_resultado_func, update_pool_status_func, ajustar_saldo_func, wait_for_code_manual_func, send_discord_webhook_func):
    email = conta['email']
    senha = conta['senha']
    nome = conta.get('nome', 'Teste Silva')
    nascimento = conta.get('nascimento', '20/05/2002')

    print(f"\n=== Criando Spotify: {email} ===")

    progress = f"🎵 {email}\n\nEstado: Iniciando cadastro..."
    msg_id = send_message_func(chat_id, progress)

    local_browser = launch(headless=False, humanize=False)
    page = local_browser.new_page()

    try:
        spotify_url = "https://www.spotify.com/br-pt/signup?flow_id=d864602a-00cc-40c3-a265-337e3e97661d%3A1782792365&forward_url=https%3A%2F%2Fwww.spotify.com%2Fbr-pt%2Fpurchase%2Foffer%2Fdefault-intro%2F%3Fcountry%3DBR%26ref%3Dspotifycom_premium_hero%26flow_ctx%3Dd864602a-00cc-40c3-a265-337e3e97661d%253A1782792365"

        page.goto(spotify_url)
        page.wait_for_load_state("networkidle")
        human_delay(3, 5)

        # ==================== EMAIL ====================
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Colocando email...")
        for sel in ["input#email", "input[name='email']", "input[type='email']"]:
            try:
                page.wait_for_selector(sel, timeout=10000)
                page.fill(sel, email)
                break
            except:
                continue

        try:
            page.click("button:has-text('Next')", timeout=5000)
        except:
            try:
                page.click("button:has-text('Continuar')", timeout=5000)
            except:
                page.keyboard.press("Enter")

        human_delay(4, 6)

        # ==================== SENHA ====================
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Colocando senha...")
        for sel in ["input#password", "input[name='password']", "input[type='password']"]:
            try:
                page.wait_for_selector(sel, timeout=10000)
                page.fill(sel, senha)
                break
            except:
                continue

        try:
            page.click("button:has-text('Next')", timeout=5000)
        except:
            try:
                page.click("button:has-text('Continuar')", timeout=5000)
            except:
                page.keyboard.press("Enter")

        human_delay(4, 6)

        # ==================== PÁGINA "FALE DE VOCÊ" ====================
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Preenchendo nome...")

        # === NOME ===
        nome_preenchido = False
        for sel in ["input#displayName", "input[name='displayName']"]:
            try:
                page.wait_for_selector(sel, timeout=10000)
                page.fill(sel, nome)
                nome_preenchido = True
                print("[SPOTIFY] ✅ Nome preenchido com sucesso")
                break
            except:
                continue

        if not nome_preenchido:
            print("[SPOTIFY] ❌ Não conseguiu preencher o nome")

        human_delay(1, 2)

        # === DATA DE NASCIMENTO ===
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Preenchendo data de nascimento...")

        try:
            dia, mes, ano = nascimento.split("/")

            # Dia
            page.wait_for_selector("input#day", timeout=10000)
            page.fill("input#day", dia)
            human_delay(0.5, 1)

            # Mês
            try:
                page.select_option("select#month", value=mes.zfill(2))
            except:
                try:
                    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
                    page.select_option("select#month", label=meses[int(mes)-1])
                except:
                    print("[SPOTIFY] Não conseguiu selecionar o mês")

            human_delay(0.5, 1)

            # Ano
            page.fill("input#year", ano)
            human_delay(1, 2)

        except Exception as e:
            print(f"[SPOTIFY] Erro na data de nascimento: {e}")

        # === GÊNERO (Mulher) ===
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Selecionando gênero...")
        try:
            page.click("label[for='gender_option_female']", timeout=6000)
        except:
            try:
                page.click("text=Mulher", timeout=5000)
            except:
                pass

        human_delay(1, 2)

        # === CLICAR EM AVANÇAR ===
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Avançando...")
        try:
            page.click("button[data-testid='submit']", timeout=8000)
        except:
            try:
                page.click("button:has-text('Avançar')", timeout=6000)
            except:
                try:
                    page.click("button[type='submit']", timeout=5000)
                except:
                    page.keyboard.press("Enter")

        human_delay(5, 7)

        # Tenta resolver reCAPTCHA se aparecer
        try:
            if page.locator("iframe[title*='reCAPTCHA']").is_visible(timeout=8000):
                edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Resolvendo reCAPTCHA...")
                site_key = page.evaluate("() => document.querySelector('.g-recaptcha')?.getAttribute('data-sitekey')")
                if site_key:
                    solve_recaptcha_2captcha(page, site_key, spotify_url)
                    page.click("button[data-testid='submit']", timeout=6000)
                    human_delay(6, 8)
        except:
            pass

        # Verificação final
        if "account" in page.url.lower() or page.locator("text=Welcome").is_visible(timeout=8000):
            edit_message_func(chat_id, msg_id, f"🎵 {email}\n\n✅ CONTA CRIADA COM SUCESSO!")
            log_resultado_func(user_id, email, "SUCESSO")
            update_pool_status_func(user_id, email, "done")
            send_discord_webhook_func(email, senha)
        else:
            edit_message_func(chat_id, msg_id, f"🎵 {email}\n\n⚠️ Pode precisar de verificação manual.")
            log_resultado_func(user_id, email, "VERIFICAR")
            update_pool_status_func(user_id, email, "verificar")

    except Exception as e:
        print(f"\n=== ERRO SPOTIFY ===\n{e}")
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\n❌ Erro: {str(e)[:80]}")
        log_resultado_func(user_id, email, "ERRO")
        update_pool_status_func(user_id, email, "erro")
        ajustar_saldo_func(chat_id, preco)

    finally:
        try:
            page.close()
            local_browser.close()
        except:
            pass
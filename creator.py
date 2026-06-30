import time
import random
import re
import requests
from cloakbrowser import launch

def human_delay(min_s=1.0, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))

def criar_conta_spotify(browser, conta, chat_id, user_id, job_id, preco, send_message_func, edit_message_func, log_resultado_func, update_pool_status_func, ajustar_saldo_func, wait_for_code_manual_func, send_discord_webhook_func):
    email = conta['email']
    senha = conta['senha']
    nome = conta.get('nome', 'Teste Silva')
    nascimento = conta.get('nascimento', '20/05/2002')

    print(f"\n=== Criando Spotify (paralelo): {email} ===")

    progress = f"🎵 {email}\n\nEstado: Iniciando cadastro Spotify..."
    msg_id = send_message_func(chat_id, progress)

    local_browser = launch(headless=False, humanize=True)
    page = local_browser.new_page()

    try:
        # ============================================
        # LINK ESPECÍFICO DO SPOTIFY (Premium)
        # ============================================
        spotify_url = "https://www.spotify.com/br-pt/signup?flow_id=d864602a-00cc-40c3-a265-337e3e97661d%3A1782792365&forward_url=https%3A%2F%2Fwww.spotify.com%2Fbr-pt%2Fpurchase%2Foffer%2Fdefault-intro%2F%3Fcountry%3DBR%26ref%3Dspotifycom_premium_hero%26flow_ctx%3Dd864602a-00cc-40c3-a265-337e3e97661d%253A1782792365"

        page.goto(spotify_url)
        page.wait_for_load_state("networkidle")
        human_delay(3, 5)

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Colocando email...")

        # === EMAIL ===
        for sel in ["input#email", "input[name='email']", "input[type='email']"]:
            try:
                page.fill(sel, email, timeout=8000)
                break
            except:
                continue

        human_delay(1, 2)
        page.keyboard.press("Enter")
        human_delay(4, 6)

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Colocando senha...")

        # === SENHA ===
        for sel in ["input#password", "input[name='password']", "input[type='password']"]:
            try:
                page.fill(sel, senha, timeout=8000)
                break
            except:
                continue

        human_delay(1, 2)
        page.keyboard.press("Enter")
        human_delay(4, 6)

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Colocando nome...")

        # === NOME ===
        for sel in ["input#displayname", "input[name='displayname']", "input[placeholder*='nome' i]"]:
            try:
                page.fill(sel, nome, timeout=8000)
                break
            except:
                continue

        human_delay(1, 2)
        page.keyboard.press("Enter")
        human_delay(4, 6)

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Preenchendo data de nascimento...")

        # === DATA DE NASCIMENTO (20 / Mês / 2002) ===
        try:
            # Dia
            page.fill("input#day", "20", timeout=6000)
            human_delay(0.5, 1)

            # Mês (select)
            page.select_option("select#month", "05")  # Maio
            human_delay(0.5, 1)

            # Ano
            page.fill("input#year", "2002", timeout=6000)
            human_delay(1, 2)
        except Exception as e:
            print(f"[SPOTIFY] Erro ao preencher data: {e}")

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Selecionando gênero...")

        # === GÊNERO (Mulher) ===
        try:
            page.click("label[for='gender_option_female']", timeout=6000)
            human_delay(1, 2)
        except:
            try:
                page.click("text=Mulher", timeout=5000)
            except:
                pass

        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\nEstado: Aceitando termos...")

        # === ACEITAR TERMOS + INSCREVER-SE ===
        try:
            page.click("input[type='checkbox']", timeout=6000)
            human_delay(1, 2)
            page.click("button[type='submit']", timeout=8000)
            human_delay(4, 6)
        except:
            pass

        # Por enquanto marca como VERIFICAR (reCAPTCHA ainda não tratado)
        edit_message_func(chat_id, msg_id, f"🎵 {email}\n\n⚠️ Fluxo em desenvolvimento (reCAPTCHA pendente).\n\nEmail: `{email}`")
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
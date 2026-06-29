import time
import random
import requests
from playwright.sync_api import sync_playwright


def human_delay(min_s=8, max_s=12):
    """Espera humana entre ações (padrão 10 segundos)"""
    time.sleep(random.uniform(min_s, max_s))


def solve_recaptcha_2captcha(page, sitekey, api_key):
    """
    Resolve reCAPTCHA v2 usando 2Captcha
    """
    print("[2CAPTCHA] Enviando reCAPTCHA para resolução...")
    
    # 1. Enviar o captcha para o 2Captcha
    url = "http://2captcha.com/in.php"
    data = {
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": sitekey,
        "pageurl": page.url,
        "json": 1
    }
    
    try:
        response = requests.post(url, data=data, timeout=30).json()
        if response.get("status") != 1:
            print(f"[2CAPTCHA] Erro ao enviar: {response}")
            return False
        
        captcha_id = response["request"]
        print(f"[2CAPTCHA] Captcha ID: {captcha_id} - Aguardando resolução...")
        
        # 2. Aguardar a resolução
        result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1"
        
        for _ in range(30):  # Espera até 5 minutos
            time.sleep(10)
            result = requests.get(result_url, timeout=10).json()
            
            if result.get("status") == 1:
                token = result["request"]
                print("[2CAPTCHA] ✅ reCAPTCHA resolvido!")
                
                # 3. Injetar o token na página
                page.evaluate(f"""
                    document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                    ___grecaptcha_cfg.clients[0].M[0].callback('{token}');
                """)
                return True
            
            if result.get("request") == "CAPCHA_NOT_READY":
                print("[2CAPTCHA] Ainda resolvendo...")
                continue
            else:
                print(f"[2CAPTCHA] Erro: {result}")
                return False
        
        print("[2CAPTCHA] Timeout esperando resolução")
        return False
        
    except Exception as e:
        print(f"[2CAPTCHA] Erro: {e}")
        return False


def create_spotify_account(email, senha, nome, nascimento, genero="Mulher"):
    """
    Cria conta no Spotify seguindo o fluxo que você passou
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()
        
        try:
            # URL direta de signup
            signup_url = "https://www.spotify.com/br-pt/signup?flow_id=d864602a-00cc-40c3-a265-337e3e97661d%3A1782792365&forward_url=https%3A%2F%2Fwww.spotify.com%2Fbr-pt%2Fpurchase%2Foffer%2Fdefault-intro%2F%3Fcountry%3DBR%26ref%3Dspotifycom_premium_hero%26flow_ctx%3Dd864602a-00cc-40c3-a265-337e3e97661d%253A1782792365"
            
            print(f"[SPOTIFY] Abrindo página de cadastro...")
            page.goto(signup_url)
            page.wait_for_load_state("networkidle")
            human_delay(3, 5)
            
            # Passo 1: Email
            print("[SPOTIFY] Preenchendo email...")
            page.fill("input[type='email']", email)
            human_delay(10, 11)
            page.click("button:has-text('Avançar')")
            
            # Passo 2: Senha
            print("[SPOTIFY] Preenchendo senha...")
            page.fill("input[type='password']", senha)
            human_delay(10, 11)
            page.click("button:has-text('Avançar')")
            
            # Passo 3: Nome
            print("[SPOTIFY] Preenchendo nome...")
            page.fill("input[name='displayName']", nome)
            human_delay(2, 3)
            
            # Passo 4: Data de nascimento
            print("[SPOTIFY] Preenchendo data de nascimento...")
            # Dia
            page.fill("input[placeholder='dd']", "20")
            human_delay(1, 2)
            
            # Mês (clicar e selecionar)
            page.click("select[name='month']")
            human_delay(1, 2)
            # Aqui você pode melhorar a seleção do mês
            
            # Ano
            page.fill("input[placeholder='aaaa']", nascimento.split("/")[2] if "/" in nascimento else "2002")
            human_delay(2, 3)
            
            # Gênero - Mulher
            print("[SPOTIFY] Selecionando gênero Mulher...")
            page.click("input[value='female']")
            human_delay(2, 3)
            
            page.click("button:has-text('Avançar')")
            human_delay(3, 5)
            
            # Passo final: Termos + Inscrever-se
            print("[SPOTIFY] Aceitando termos...")
            page.check("input[type='checkbox']")
            human_delay(2, 3)
            
            page.click("button:has-text('Inscrever-se')")
            human_delay(5, 7)
            
            # Verifica se apareceu reCAPTCHA
            if page.locator("text=Precisamos ter certeza de que você é um ser humano").is_visible():
                print("[SPOTIFY] reCAPTCHA detectado! Resolvendo com 2Captcha...")
                # Aqui vamos implementar o resolve_recaptcha
                
            print("[SPOTIFY] Processo finalizado!")
            
        except Exception as e:
            print(f"[SPOTIFY] Erro: {e}")
        finally:
            browser.close()

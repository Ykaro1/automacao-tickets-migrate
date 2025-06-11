import os
import time
import pandas as pd
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Bibliotecas do Selenium ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException

# --- CONFIGURAÇÕES E CREDENCIAIS ---
MIGRATE_EMAIL = os.getenv("MIGRATE_EMAIL")
MIGRATE_SENHA = os.getenv("MIGRATE_SENHA")

def verificar_variaveis_ambiente():
    """Verifica se todas as variáveis de ambiente necessárias estão configuradas."""
    variaveis_necessarias = {
        "MIGRATE_EMAIL": MIGRATE_EMAIL,
        "MIGRATE_SENHA": MIGRATE_SENHA
    }
    variaveis_faltantes = [var for var, valor in variaveis_necessarias.items() if not valor]
    if variaveis_faltantes:
        print("ERRO: As seguintes variáveis de ambiente não foram configuradas no arquivo .env:")
        for var in variaveis_faltantes:
            print(f"- {var}")
        return False
    return True

def iniciar_navegador():
    """Inicia o navegador Chrome em modo headless."""
    try:
        # Configura o diretório de downloads
        download_dir = os.path.abspath("downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # Configura as opções do Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Configura o diretório de downloads
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Inicia o navegador
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        return driver, download_dir
        
    except Exception as e:
        print(f"ERRO ao iniciar o navegador: {str(e)}")
        return None, None

def login_e_download(driver, email, senha):
    """Realiza o login na plataforma e faz o download do relatório de tickets."""
    try:
        print("Iniciando o navegador Chrome em modo headless...")
        driver.get("https://app.migrate.com.br/relatorios")
        time.sleep(15)  # Aumentado para 15 segundos
        
        print("Inserindo credenciais...")
        # Aguarda e preenche o campo de email
        email_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        email_input.clear()
        email_input.send_keys(email)
        
        # Aguarda e preenche o campo de senha
        senha_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "password"))
        )
        senha_input.clear()
        senha_input.send_keys(senha)
        
        # Aguarda e clica no botão de login
        login_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Entrar')]"))
        )
        login_button.click()
        
        print("Login realizado. Aguardando carregamento da página...")
        time.sleep(10)  # Aumentado para 10 segundos
        
        # Verifica se há tela de confirmação
        try:
            confirm_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Confirmar')]"))
            )
            confirm_button.click()
            print("Tela de confirmação encontrada e confirmada.")
        except TimeoutException:
            print("Nenhuma tela de confirmação apareceu. Continuando...")
        
        # Aguarda carregamento da página principal
        time.sleep(15)  # Aumentado para 15 segundos
        
        # Tenta encontrar o botão OPÇÕES usando JavaScript
        print("Procurando botão OPÇÕES...")
        opcoes_button = driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('OPÇÕES') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not opcoes_button:
            raise Exception("Botão OPÇÕES não encontrado")
        
        print("Botão OPÇÕES encontrado, clicando...")
        driver.execute_script("arguments[0].click();", opcoes_button)
        time.sleep(5)
        
        # Tenta encontrar o botão EXPORTAR usando JavaScript
        print("Procurando botão EXPORTAR...")
        exportar_button = driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('EXPORTAR') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not exportar_button:
            raise Exception("Botão EXPORTAR não encontrado")
        
        print("Botão EXPORTAR encontrado, clicando...")
        driver.execute_script("arguments[0].click();", exportar_button)
        time.sleep(5)
        
        # Tenta encontrar o botão EXCEL usando JavaScript
        print("Procurando botão EXCEL...")
        excel_button = driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('EXCEL') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not excel_button:
            raise Exception("Botão EXCEL não encontrado")
        
        print("Botão EXCEL encontrado, clicando...")
        driver.execute_script("arguments[0].click();", excel_button)
        
        # Aguarda o download
        print("Aguardando download do arquivo...")
        time.sleep(30)  # Aumentado para 30 segundos
        
        return True
        
    except Exception as e:
        print(f"Erro durante o login e download: {str(e)}")
        return False

if __name__ == "__main__":
    driver = None
    try:
        if not verificar_variaveis_ambiente():
            raise Exception("Variáveis de ambiente não configuradas.")
            
        driver, download_dir = iniciar_navegador()
        if driver and download_dir:
            login_e_download(driver, MIGRATE_EMAIL, MIGRATE_SENHA)
        else:
            print("ERRO: Não foi possível iniciar o navegador.")

    except Exception as e:
        print(f"\n--- ERRO CRÍTICO NA EXECUÇÃO DO SCRIPT: {e} ---")
    finally:
        if driver:
            print("\nFechando o navegador...")
            driver.quit()
        print("Execução finalizada.")
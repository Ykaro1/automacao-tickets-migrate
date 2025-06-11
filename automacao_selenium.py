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

def analisar_excel(arquivo_excel):
    """Analisa o arquivo Excel e conta os tickets ativos."""
    try:
        print(f"\nAnalisando arquivo: {arquivo_excel}")
        # Lê o arquivo Excel
        df = pd.read_excel(arquivo_excel)
        
        # Verifica se a coluna 'Status' existe
        if 'Status' not in df.columns:
            print("ERRO: Coluna 'Status' não encontrada no arquivo Excel")
            print(f"Colunas encontradas: {df.columns.tolist()}")
            return
        
        # Filtra os tickets que não estão fechados ou resolvidos
        tickets_ativos = df[~df['Status'].isin(['Fechado', 'Resolvido'])]
        
        # Conta quantos tickets ativos existem
        total_ativos = len(tickets_ativos)
        
        print(f"\nTotal de tickets ativos: {total_ativos}")
        
        # Mostra os status únicos dos tickets ativos
        print("\nStatus únicos dos tickets ativos:")
        for status in tickets_ativos['Status'].unique():
            count = len(tickets_ativos[tickets_ativos['Status'] == status])
            print(f"- {status}: {count} tickets")
        
        # Mostra os primeiros 5 tickets ativos
        if total_ativos > 0:
            print("\nPrimeiros 5 tickets ativos:")
            print(tickets_ativos[['Número', 'Status', 'Título']].head().to_string())
        
    except Exception as e:
        print(f"ERRO ao analisar o arquivo Excel: {str(e)}")

def iniciar_navegador():
    """Inicia o navegador Chrome."""
    try:
        # Configura o diretório de downloads
        download_dir = os.path.abspath("downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # Configura as opções do Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Modo headless
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Configura o diretório de downloads
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Inicia o navegador
        print("Iniciando o navegador Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        return driver, download_dir
        
    except Exception as e:
        print(f"ERRO ao iniciar o navegador: {str(e)}")
        return None, None

def login_e_download(driver, download_dir):
    """Realiza o login e faz o download do arquivo."""
    try:
        # Acessa a página de login
        print("Inserindo credenciais...")
        driver.get("https://atendimento.migrate.com.br/Ticket")
        time.sleep(10)  # Aumentado para 10 segundos
        
        # Aguarda e preenche o email
        print("Procurando campo de e-mail...")
        email_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
        )
        email_input.clear()  # Limpa o campo antes de inserir
        time.sleep(1)  # Pequena pausa após limpar
        email_input.send_keys(MIGRATE_EMAIL)
        print("E-mail inserido com sucesso")
        
        # Aguarda e preenche a senha
        print("Procurando campo de senha...")
        password_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
        )
        password_input.clear()  # Limpa o campo antes de inserir
        time.sleep(1)  # Pequena pausa após limpar
        password_input.send_keys(MIGRATE_SENHA)
        print("Senha inserida com sucesso")
        
        # Clica no botão de login
        print("Procurando botão de login...")
        login_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button-login"))
        )
        login_button.click()
        print("Botão de login clicado")
        
        # Aguarda o carregamento da página
        print("Login realizado. Aguardando carregamento da página...")
        time.sleep(10)  # Aumentado para 10 segundos
        
        # Verifica se há tela de confirmação
        try:
            confirm_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-mv-confirm[data-value='yes']"))
            )
            confirm_button.click()
            print("Tela de confirmação encontrada e confirmada.")
        except:
            print("Nenhuma tela de confirmação encontrada.")
        
        # Aguarda mais um pouco para garantir que a página carregou completamente
        time.sleep(5)
        
        # Procura e clica no botão OPÇÕES
        print("Procurando botão OPÇÕES...")
        opcoes_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'button-text') and text()='OPÇÕES']"))
        )
        print("Botão OPÇÕES encontrado, clicando...")
        opcoes_button.click()
        
        # Aguarda um pouco após clicar em OPÇÕES
        time.sleep(2)
        
        # Procura e clica no link de exportar para Excel
        print("Procurando link de exportar para Excel...")
        exportar_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btnExport.btnExportToExcel"))
        )
        print("Link de exportar encontrado, clicando...")
        exportar_link.click()
        
        # Aguarda o modal de opções aparecer
        time.sleep(2)
        
        # Seleciona a opção "Todas as ações na mesma coluna"
        print("Selecionando opção de exportação...")
        select_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select.col-xs-12.input-mv-new.md-confirm-options"))
        )
        select = Select(select_element)
        select.select_by_value("3")  # Valor 3 corresponde a "Todas as ações na mesma coluna"
        print("Opção selecionada com sucesso")
        
        # Clica no botão OK
        print("Procurando botão OK...")
        ok_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-mv.btn-mv-confirm.md-confirm-action.trigger-service-nps[data-value='ok']"))
        )
        ok_button.click()
        print("Botão OK clicado")
        
        # Aguarda o download
        print("Aguardando download...")
        time.sleep(30)  # Aumentado para 30 segundos
        
        # Verifica se o arquivo foi baixado
        print("Verificando arquivos no diretório de downloads...")
        arquivos = os.listdir(download_dir)
        print(f"Arquivos encontrados: {arquivos}")
        
        # Tenta encontrar o arquivo Excel mais recente
        arquivos_excel = [f for f in arquivos if f.endswith('.xlsx')]
        if arquivos_excel:
            # Pega o arquivo mais recente
            arquivo_excel = max(arquivos_excel, key=lambda x: os.path.getctime(os.path.join(download_dir, x)))
            print(f"Arquivo baixado com sucesso: {arquivo_excel}")
            
            # Analisa o arquivo Excel
            caminho_completo = os.path.join(download_dir, arquivo_excel)
            analisar_excel(caminho_completo)
            
            return True
        else:
            print("Nenhum arquivo Excel encontrado no diretório de downloads")
            # Tira um screenshot para debug
            screenshot_path = os.path.join(download_dir, "erro_download.png")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot salvo em: {screenshot_path}")
            return False
            
    except Exception as e:
        print(f"Erro durante o login e download: {str(e)}")
        # Tira um screenshot em caso de erro
        try:
            screenshot_path = os.path.join(download_dir, "erro.png")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot salvo em: {screenshot_path}")
        except:
            print("Não foi possível salvar o screenshot")
        return False

def main():
    """Função principal."""
    try:
        print("Iniciando automação...")
        driver, download_dir = iniciar_navegador()
        if driver and download_dir:
            login_e_download(driver, download_dir)
        else:
            print("ERRO: Não foi possível iniciar o navegador.")
    except Exception as e:
        print(f"ERRO durante a execução: {str(e)}")
    finally:
        if 'driver' in locals():
            print("\nFechando o navegador...")
            driver.quit()
        print("Execução finalizada.")

if __name__ == "__main__":
    main()
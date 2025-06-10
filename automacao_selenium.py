import os
import time
import pandas as pd
from datetime import datetime
import requests
import json
import google.generativeai as genai

# --- Bibliotecas do Selenium (mantidas do seu código original) ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# --- CONFIGURAÇÕES E CREDENCIAIS ---
# Lendo credenciais das variáveis de ambiente
MIGRATE_EMAIL = os.getenv("MIGRATE_EMAIL")
MIGRATE_SENHA = os.getenv("MIGRATE_SENHA")
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

# Verificação das variáveis de ambiente
def verificar_variaveis_ambiente():
    variaveis_necessarias = {
        "MIGRATE_EMAIL": MIGRATE_EMAIL,
        "MIGRATE_SENHA": MIGRATE_SENHA,
        "GOOGLE_AI_API_KEY": GOOGLE_AI_API_KEY,
        "SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL,
        "SLACK_CHANNEL": SLACK_CHANNEL
    }
    
    variaveis_faltantes = [var for var, valor in variaveis_necessarias.items() if not valor]
    
    if variaveis_faltantes:
        print("ERRO: As seguintes variáveis de ambiente não foram configuradas:")
        for var in variaveis_faltantes:
            print(f"- {var}")
        print("\nPor favor, configure estas variáveis de ambiente antes de executar o script.")
        print("No GitHub Actions, você pode configurá-las em:")
        print("Settings > Secrets and variables > Actions")
        return False
    
    return True

# Nome do arquivo para guardar o estado dos tickets abertos
ARQUIVO_ACOMPANHAMENTO = "tickets_em_acompanhamento.csv"

def iniciar_navegador():
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Configuração do diretório de downloads
        download_dir = os.path.abspath(os.path.join(os.getcwd(), "downloads"))
        print(f"\nConfigurando diretório de downloads: {download_dir}")
        
        if not os.path.exists(download_dir):
            print("Criando diretório de downloads...")
            os.makedirs(download_dir)
        
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "download.default_content_settings.popups": 0,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        print("Iniciando o navegador Chrome...")
        driver = webdriver.Chrome(options=chrome_options)
        return driver, download_dir
    except Exception as e:
        print(f"Erro ao iniciar o navegador: {str(e)}")
        raise

def esperar_elemento(driver, by, value, timeout=20):
    try:
        elemento = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return elemento
    except TimeoutException:
        print(f"Timeout ao esperar elemento: {value}")
        return None
    except Exception as e:
        print(f"Erro ao esperar elemento {value}: {str(e)}")
        return None

def login_e_download(driver, email, senha):
    try:
        driver.get("https://atendimento.migrate.com.br/Ticket")
        time.sleep(10)
        
        print("Procurando campo de email...")
        email_field = esperar_elemento(driver, By.CSS_SELECTOR, 'input.form-control.mv-input-radius.p-5.username-input-login-service[type="text"]')
        if not email_field: raise Exception("Campo de email não encontrado")
        email_field.clear()
        time.sleep(1)
        email_field.send_keys(email)
        print("Email inserido.")
        
        time.sleep(2)
        
        print("Procurando campo de senha...")
        senha_field = esperar_elemento(driver, By.CSS_SELECTOR, 'input.form-control.mv-input-radius.p-5.password-input-login-service[type="password"]')
        if not senha_field: raise Exception("Campo de senha não encontrado")
        senha_field.clear()
        time.sleep(1)
        senha_field.send_keys(senha)
        print("Senha inserida.")
        
        time.sleep(2)
        
        print("Procurando botão de login...")
        login_button = esperar_elemento(driver, By.CSS_SELECTOR, 'button.btn.button-color-login.col-xs-5.mv-button-radius.login-button.button-login.ui-md-login-button')
        if not login_button: raise Exception("Botão de login não encontrado")
        login_button.click()
        print("Botão de login clicado!")
        
        time.sleep(10)
        print("Login realizado com sucesso!")

        try:
            print("Verificando se existe tela de confirmação...")
            botao_sim = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.btn-mv.btn-mv-confirm.md-confirm-action[data-value="yes"]'))
            )
            print("Botão 'Sim' encontrado! Clicando...")
            botao_sim.click()
            time.sleep(3)
        except Exception:
            print("Tela de confirmação não apareceu. Continuando...")

        print("Procurando botão OPÇÕES...")
        opcoes_button = esperar_elemento(driver, By.XPATH, "//span[contains(text(), 'OPÇÕES')]")
        if not opcoes_button: raise Exception("Botão OPÇÕES não encontrado")
        opcoes_button.click()
        print("Botão OPÇÕES clicado!")
        time.sleep(5)
        
        print("Procurando botão Exportar para Excel...")
        excel_button = esperar_elemento(driver, By.CSS_SELECTOR, 'a.btnExport.btnExportToExcel[data-export-to="Excel"]')
        if not excel_button: raise Exception("Botão Exportar para Excel não encontrado")
        excel_button.click()
        print("Botão Exportar para Excel clicado!")
        time.sleep(5)
        
        print("Procurando seletor de opções...")
        opcoes_select = esperar_elemento(driver, By.CSS_SELECTOR, 'select.col-xs-12.input-mv-new.md-confirm-options')
        if not opcoes_select: raise Exception("Seletor de opções não encontrado")
        select = Select(opcoes_select)
        select.select_by_value("3")
        print("Opção 'Todas as ações na mesma coluna' selecionada!")
        time.sleep(3)
        
        print("Procurando botão Ok...")
        ok_button = esperar_elemento(driver, By.CSS_SELECTOR, 'button.btn-mv.btn-mv-confirm.md-confirm-action.trigger-service-nps[data-value="ok"]')
        if not ok_button: raise Exception("Botão Ok não encontrado")
        ok_button.click()
        print("Botão Ok clicado!")
        
        # Verificação do download
        download_dir = os.path.join(os.getcwd(), "downloads")
        print(f"\nIniciando verificação do download no diretório: {download_dir}")
        
        # Aguarda até 60 segundos pelo download
        max_tentativas = 12
        for tentativa in range(max_tentativas):
            print(f"\nVerificação {tentativa + 1} de {max_tentativas}")
            
            # Lista todos os arquivos no diretório
            arquivos = os.listdir(download_dir)
            print(f"Arquivos encontrados: {arquivos}")
            
            # Verifica se há downloads em andamento
            arquivos_crdownload = [f for f in arquivos if f.endswith('.crdownload')]
            if arquivos_crdownload:
                print(f"Downloads em andamento: {arquivos_crdownload}")
                time.sleep(5)
                continue
            
            # Verifica se há arquivos Excel
            arquivos_excel = [f for f in arquivos if f.endswith('.xlsx')]
            if arquivos_excel:
                print(f"Arquivo Excel encontrado: {arquivos_excel[0]}")
                print("Download concluído com sucesso!")
                return
            
            print("Aguardando 5 segundos para próxima verificação...")
            time.sleep(5)
        
        raise Exception("Tempo limite excedido aguardando o download do arquivo Excel")
        
    except Exception as e:
        print(f"Erro durante o processo de login e download: {str(e)}")
        driver.quit()
        raise

def ler_excel_recente(download_dir):
    try:
        print("\nProcurando arquivo Excel baixado...")
        print(f"Diretório de busca: {download_dir}")
        
        # Verifica se o diretório existe
        if not os.path.exists(download_dir):
            print(f"ERRO: Diretório {download_dir} não existe!")
            return None
            
        # Lista todos os arquivos no diretório
        arquivos = os.listdir(download_dir)
        print(f"Arquivos encontrados no diretório: {arquivos}")
        
        # Filtra apenas arquivos Excel
        arquivos_excel = [f for f in arquivos if f.endswith('.xlsx')]
        print(f"Arquivos Excel encontrados: {arquivos_excel}")
        
        if not arquivos_excel:
            print("Nenhum arquivo Excel encontrado!")
            return None
        
        # Encontra o arquivo mais recente
        arquivo_mais_recente = max(arquivos_excel, key=lambda x: os.path.getctime(os.path.join(download_dir, x)))
        caminho_arquivo = os.path.join(download_dir, arquivo_mais_recente)
        
        print(f"Lendo o arquivo: {arquivo_mais_recente}")
        print(f"Caminho completo: {caminho_arquivo}")
        
        # Verifica se o arquivo existe e tem tamanho maior que 0
        if not os.path.exists(caminho_arquivo):
            print(f"ERRO: Arquivo {caminho_arquivo} não existe!")
            return None
            
        if os.path.getsize(caminho_arquivo) == 0:
            print(f"ERRO: Arquivo {caminho_arquivo} está vazio!")
            return None
        
        df = pd.read_excel(caminho_arquivo)
        
        print("\nPrimeiras 5 linhas do arquivo original:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"Erro ao ler o arquivo Excel: {str(e)}")
        return None

def analisar_com_ia(texto_acao, api_key):
    """Envia o texto da ação para a IA do Google para gerar um resumo."""
    try:
        print(f"   - Enviando ação para análise da IA...")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Resuma a seguinte atualização de um ticket de suporte em uma única frase, como se fosse um status rápido para uma equipe.
        Seja direto e informativo.
        
        Texto da atualização:
        "{texto_acao}"

        Resumo:
        """
        
        response = model.generate_content(prompt)
        resumo = response.text.strip()
        print(f"   - Resumo da IA: '{resumo}'")
        return resumo
    except Exception as e:
        print(f"   - ERRO ao contatar a IA: {str(e)}")
        # Em caso de erro com a IA, retorna os 150 primeiros caracteres da ação original
        return (texto_acao[:150] + '...') if len(texto_acao) > 150 else texto_acao

def enviar_notificacao_slack(webhook_url, channel, ticket):
    """Envia uma notificação formatada para o Slack."""
    try:
        # Gera o resumo da última ação usando a IA
        resumo_ia = analisar_com_ia(ticket['Ações'], GOOGLE_AI_API_KEY)
        
        mensagem = f"Ticket #{ticket['Número']} atualizado!"

        # Usando o Block Kit do Slack para uma mensagem mais bonita
        payload = {
            "channel": channel,
            "text": mensagem, # Texto de fallback para notificações
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"✅ Ticket Atualizado: #{ticket['Número']}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Assunto:*\n{ticket['Assunto']}"},
                        {"type": "mrkdwn", "text": f"*Responsável:*\n{ticket['Responsável']}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Resumo da Última Ação (via IA):*\n>{resumo_ia}"
                    }
                }
            ]
        }
        
        print(f"   - Enviando notificação para o Slack...")
        response = requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            print("   - Notificação enviada com sucesso ao Slack!")
        else:
            print(f"   - ERRO ao enviar para o Slack: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"   - ERRO GERAL ao tentar notificar: {str(e)}")

def analisar_e_acompanhar_tickets(df_atual):
    """Função principal que analisa, compara e dispara notificações."""
    if df_atual is None or df_atual.empty:
        print("DataFrame vazio ou nulo. Nenhuma análise será feita.")
        return

    # 1. Filtrar tickets que NÃO estão Fechados ou Resolvidos
    status_excluidos = ["Fechado", "Resolvido"]
    df_abertos_atual = df_atual[~df_atual['Status'].fillna('').isin(status_excluidos)].copy()
    
    # Garantir que as colunas principais não tenham valores nulos e sejam do tipo string
    for col in ['Número', 'Ações', 'Status']:
        if col in df_abertos_atual.columns:
            df_abertos_atual[col] = df_abertos_atual[col].astype(str).fillna('N/A')

    print(f"\nEncontrados {len(df_abertos_atual)} tickets com status diferente de 'Fechado' ou 'Resolvido'.")

    # 2. Verificar se o arquivo de acompanhamento existe
    if not os.path.exists(ARQUIVO_ACOMPANHAMENTO):
        print(f"Arquivo '{ARQUIVO_ACOMPANHAMENTO}' não encontrado. Criando novo arquivo de acompanhamento.")
        print("Nenhuma notificação será enviada nesta primeira execução.")
        df_abertos_atual.to_csv(ARQUIVO_ACOMPANHAMENTO, index=False)
        return

    # 3. Se o arquivo existe, carregar os dados antigos e comparar
    print(f"Carregando dados do arquivo de acompanhamento '{ARQUIVO_ACOMPANHAMENTO}'...")
    df_abertos_antigo = pd.read_csv(ARQUIVO_ACOMPANHAMENTO, dtype=str).fillna('N/A')
    
    # Unir os dataframes antigo e novo com base no número do ticket
    # 'indicator=True' cria uma coluna '_merge' que nos diz a origem de cada linha
    df_merged = pd.merge(
        df_abertos_antigo, 
        df_abertos_atual, 
        on='Número', 
        how='outer', 
        suffixes=('_antigo', '_atual'),
        indicator=True
    )

    # 4. Iterar sobre os tickets e verificar mudanças
    print("\nComparando tickets atuais com a execução anterior...")
    for index, row in df_merged.iterrows():
        # Caso 1: Ticket existia antes e ainda existe. VERIFICAR MUDANÇA.
        if row['_merge'] == 'both':
            # Compara a coluna 'Ações' antiga com a nova
            if row['Ações_antigo'] != row['Ações_atual']:
                print(f"\n[!] MUDANÇA DETECTADA no Ticket #{row['Número']}")
                ticket_info = {
                    'Número': row['Número'],
                    'Assunto': row['Assunto_atual'],
                    'Responsável': row['Responsável_atual'],
                    'Ações': row['Ações_atual']
                }
                enviar_notificacao_slack(SLACK_WEBHOOK_URL, SLACK_CHANNEL, ticket_info)

        # Caso 2: Ticket é novo (só existe na planilha atual).
        elif row['_merge'] == 'right_only':
            print(f"\n[+] NOVO TICKET ABERTO DETECTADO: #{row['Número']}")
            # Você pode decidir se quer notificar sobre novos tickets também
            # Por enquanto, vamos apenas registrar.
        
        # Caso 3: Ticket foi fechado/resolvido (só existia na planilha antiga).
        elif row['_merge'] == 'left_only':
            print(f"\n[-] TICKET FECHADO/RESOLVIDO: #{row['Número']}")
            # Nenhuma ação necessária, pois ele não estará mais na lista de acompanhamento.

    # 5. Salvar o estado atual para a próxima execução
    print(f"\nAtualizando o arquivo de acompanhamento '{ARQUIVO_ACOMPANHAMENTO}' com os dados mais recentes.")
    df_abertos_atual.to_csv(ARQUIVO_ACOMPANHAMENTO, index=False)
    print("Análise concluída.")


if __name__ == "__main__":
    driver = None
    try:
        # Verifica se todas as variáveis de ambiente necessárias estão configuradas
        if not verificar_variaveis_ambiente():
            raise Exception("Variáveis de ambiente não configuradas corretamente")
            
        # Etapa 1: Iniciar navegador e baixar o arquivo
        driver, download_dir = iniciar_navegador()
        login_e_download(driver, MIGRATE_EMAIL, MIGRATE_SENHA)
        
        # Etapa 2: Ler o arquivo Excel baixado
        df_principal = ler_excel_recente(download_dir)
        
        # Etapa 3: Analisar os dados, comparar e notificar se houver mudanças
        if df_principal is not None:
            analisar_e_acompanhar_tickets(df_principal)
        else:
            print("Não foi possível ler o arquivo Excel. O script será encerrado.")

    except Exception as e:
        print(f"\n--- ERRO CRÍTICO NA EXECUÇÃO DO SCRIPT ---")
        print(f"Detalhes: {str(e)}")
    finally:
        # Garante que o navegador seja fechado no final
        if driver:
            print("\nFechando o navegador...")
            driver.quit()
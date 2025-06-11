import os
import time
import pandas as pd
import requests
import json
import google.generativeai as genai
from dotenv import load_dotenv
import re

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
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

# Carrega a lista de autores internos do .env e a transforma em uma lista Python
AUTORES_INTERNOS_STR = os.getenv("AUTORES_INTERNOS", "")
AUTORES_INTERNOS = [autor.strip() for autor in AUTORES_INTERNOS_STR.split(',') if autor.strip()]

# Nome do arquivo para guardar o estado dos tickets acompanhados
ARQUIVO_ACOMPANHAMENTO = "tickets_em_acompanhamento.csv"

def verificar_variaveis_ambiente():
    """Verifica se todas as variáveis de ambiente necessárias estão configuradas."""
    variaveis_necessarias = {
        "MIGRATE_EMAIL": MIGRATE_EMAIL,
        "MIGRATE_SENHA": MIGRATE_SENHA,
        "GOOGLE_AI_API_KEY": GOOGLE_AI_API_KEY,
        "SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL,
        "SLACK_CHANNEL": SLACK_CHANNEL,
        "AUTORES_INTERNOS": AUTORES_INTERNOS_STR
    }
    variaveis_faltantes = [var for var, valor in variaveis_necessarias.items() if not valor]
    if variaveis_faltantes:
        print("ERRO: As seguintes variáveis de ambiente não foram configuradas no arquivo .env:")
        for var in variaveis_faltantes:
            print(f"- {var}")
        if "AUTORES_INTERNOS" in variaveis_faltantes:
            print("\nNOTA: A variável 'AUTORES_INTERNOS' é crucial e deve conter os nomes da sua equipe, separados por vírgula.")
        return False
    print("Autores internos configurados para serem ignorados:", AUTORES_INTERNOS)
    return True

def iniciar_navegador():
    """Configura e inicia o navegador Chrome em modo headless."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        download_dir = os.path.abspath("downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        prefs = {"download.default_directory": download_dir}
        chrome_options.add_experimental_option("prefs", prefs)
        
        print("Iniciando o navegador Chrome em modo headless...")
        driver = webdriver.Chrome(options=chrome_options)
        return driver, download_dir
    except Exception as e:
        print(f"Erro ao iniciar o navegador: {str(e)}")
        raise

def esperar_elemento(driver, by, value, timeout=20):
    """Aguarda um elemento estar presente na página."""
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        print(f"Timeout: Elemento não encontrado -> {value}")
        return None

def login_e_download(driver, email, senha):
    """Realiza o login na plataforma e faz o download do relatório de tickets."""
    try:
        driver.get("https://atendimento.migrate.com.br/Ticket")
        
        print("Inserindo credenciais...")
        email_field = esperar_elemento(driver, By.CSS_SELECTOR, 'input.username-input-login-service')
        if not email_field: raise Exception("Campo de email não encontrado")
        email_field.send_keys(email)

        senha_field = esperar_elemento(driver, By.CSS_SELECTOR, 'input.password-input-login-service')
        if not senha_field: raise Exception("Campo de senha não encontrado")
        senha_field.send_keys(senha)

        login_button = esperar_elemento(driver, By.CSS_SELECTOR, 'button.button-login')
        if not login_button: raise Exception("Botão de login não encontrado")
        login_button.click()
        print("Login realizado. Aguardando carregamento da página...")
        time.sleep(10)

        try:
            botao_sim = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.btn-mv-confirm[data-value="yes"]')))
            print("Tela de confirmação encontrada. Clicando em 'Sim'.")
            botao_sim.click()
            time.sleep(3)
        except TimeoutException:
            print("Nenhuma tela de confirmação apareceu. Continuando...")

        print("Navegando para o download do relatório...")
        opcoes_button = esperar_elemento(driver, By.XPATH, "//span[contains(text(), 'OPÇÕES')]")
        if not opcoes_button: raise Exception("Botão OPÇÕES não encontrado")
        opcoes_button.click(); time.sleep(2)
        excel_button = esperar_elemento(driver, By.CSS_SELECTOR, 'a.btnExportToExcel')
        if not excel_button: raise Exception("Botão Exportar para Excel não encontrado")
        excel_button.click(); time.sleep(2)
        opcoes_select = esperar_elemento(driver, By.CSS_SELECTOR, 'select.md-confirm-options')
        if not opcoes_select: raise Exception("Seletor de opções de exportação não encontrado")
        Select(opcoes_select).select_by_value("3")
        ok_button = esperar_elemento(driver, By.CSS_SELECTOR, 'button.md-confirm-action[data-value="ok"]')
        if not ok_button: raise Exception("Botão OK para confirmar download não encontrado")
        ok_button.click()
        
        print("Download iniciado. Aguardando conclusão...")
        for _ in range(30):
            time.sleep(5)
            if any(f.endswith('.xlsx') for f in os.listdir(os.path.abspath("downloads"))):
                print("Download do arquivo Excel concluído!")
                return
        raise Exception("Tempo limite excedido aguardando o download do arquivo Excel.")
        
    except Exception as e:
        print(f"Erro durante o login e download: {str(e)}")
        raise

def ler_e_processar_excel(download_dir):
    """Localiza, lê e valida o arquivo Excel mais recente."""
    print("\n--- ETAPA 1: LENDO E PROCESSANDO O ARQUIVO EXCEL ---")
    try:
        arquivos_excel = [f for f in os.listdir(download_dir) if f.endswith('.xlsx')]
        if not arquivos_excel:
            print("ERRO: Nenhum arquivo Excel (.xlsx) encontrado no diretório de downloads.")
            return None
        
        caminho_arquivo = os.path.join(download_dir, max(arquivos_excel, key=lambda x: os.path.getmtime(os.path.join(download_dir, x))))
        print(f"Lendo o arquivo: {os.path.basename(caminho_arquivo)}")
        
        try:
            df = pd.read_excel(caminho_arquivo)
        except Exception as e:
            print(f"ERRO: Falha ao ler o arquivo Excel com pandas: {e}")
            # Tenta ler o início do arquivo como texto para depuração
            try:
                with open(caminho_arquivo, 'r', errors='ignore') as f:
                    print("--- Início do conteúdo do arquivo baixado (para depuração) ---")
                    print(f.read(500))
                    print("--- Fim do conteúdo do arquivo baixado ---")
            except Exception as read_err:
                print(f"Não foi possível ler o conteúdo do arquivo para depuração: {read_err}")
            return None

        colunas_necessarias = ['Número', 'Status', 'Ações', 'Data da última ação', 'Assunto', 'Responsável']
        if any(col not in df.columns for col in colunas_necessarias):
            print("ERRO: Colunas essenciais não encontradas no arquivo Excel.")
            print(f"Colunas encontradas: {df.columns.tolist()}")
            return None

        for col in ['Assunto', 'Responsável', 'Status']:
            df[col] = df[col].astype(str).str.strip()
        
        for col in ['Número', 'Ações', 'Data da última ação']:
            df[col] = df[col].astype(str).fillna('N/A')
        
        print(f"Arquivo lido com sucesso. Total de {len(df)} tickets encontrados.")
        return df
    except Exception as e:
        print(f"ERRO CRÍTICO ao ler ou processar o arquivo Excel: {str(e)}")
        return None

def extrair_ultima_acao_e_autor(acoes_texto):
    """Extrai o texto da última ação e o nome do seu autor. Retorna uma tupla (texto_da_acao, nome_do_autor)."""
    if not isinstance(acoes_texto, str) or acoes_texto == 'N/A':
        return "Nenhuma ação registrada.", "Desconhecido"

    partes = acoes_texto.split('-----------------------------')
    ultima_acao_bloco = partes[-1].strip()
    if not ultima_acao_bloco and len(partes) > 1:
        ultima_acao_bloco = partes[-2].strip()

    match = re.search(r"Ação criada por (.+?) em \d{2}/\d{2}/\d{4}", ultima_acao_bloco)
    if match:
        autor = match.group(1).strip()
        texto_limpo = re.sub(r"^\d+ - Ação criada por .+ em \d{2}/\d{2}/\d{4}\s*", "", ultima_acao_bloco, count=1).strip()
        return texto_limpo, autor
    else:
        return ultima_acao_bloco, "Autor não identificado"

def formatar_com_ia(texto_acao, api_key):
    """Usa a IA para limpar e formatar o texto da ação para melhor legibilidade no Slack."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Você é um assistente de formatação. Sua tarefa é pegar o texto bruto de uma atualização de ticket e limpá-lo para ser postado no Slack.
        REGRAS:
        1. NÃO RESUMA. Mantenha o conteúdo original da mensagem.
        2. Remova texto desnecessário como saudações ("Bom dia", "tudo bem?"), despedidas e assinaturas de e-mail completas (avisos de confidencialidade, etc).
        3. Use a formatação Markdown do Slack para melhorar a leitura:
            - Use `*negrito*` para destacar pontos chave.
            - Isole mensagens de erro ou trechos de código com ``` ```.
        Texto bruto:
        ---
        {texto_acao}
        ---
        Apresente apenas o texto formatado, pronto para ser copiado e colado.
        """
        response = model.generate_content(prompt)
        texto_formatado = response.text.strip()
        print(f"   - Texto formatado pela IA.")
        return texto_formatado
    except Exception as e:
        print(f"   - ERRO ao formatar com IA, usando texto bruto. Detalhes: {str(e)}")
        return texto_acao

def enviar_notificacao_slack(webhook_url, channel, ticket_info):
    """Envia uma notificação formatada para o Slack."""
    try:
        texto_formatado = ticket_info['Ações']
        payload = {
            "channel": channel,
            "text": f"Ticket #{ticket_info['Número']} atualizado!",
            "blocks": [
                {"type": "header", "text": { "type": "plain_text", "text": f"🔔 Resposta Recebida: Ticket #{ticket_info['Número']}", "emoji": True }},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Assunto:*\n{ticket_info['Assunto']}"},
                    {"type": "mrkdwn", "text": f"*Responsável:*\n{ticket_info['Responsável']}"}
                ]},
                {"type": "section", "text": { "type": "mrkdwn", "text": f"*Última Atualização (por {ticket_info['Autor']}):*\n>{texto_formatado}" }}
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

def analisar_e_notificar_mudancas(df_atual):
    """Analisa os tickets, compara, e notifica apenas sobre respostas de autores externos."""
    if df_atual is None: return

    print("\n--- ETAPA 2: ANALISANDO TICKETS E DETECTANDO RESPOSTAS EXTERNAS ---")

    # Lista de status que indicam tickets não ativos
    status_excluidos = ["Fechado", "Resolvido", "Cancelado", "Concluído"]
    
    # Converte todos os status para título (primeira letra maiúscula)
    df_atual['Status'] = df_atual['Status'].str.title()
    
    # Filtra os tickets ativos
    df_ativos = df_atual[~df_atual['Status'].isin(status_excluidos)].copy()
    
    # Extrai o autor da última ação
    df_ativos['Autor da Última Ação'] = df_ativos['Ações'].apply(lambda x: extrair_ultima_acao_e_autor(x)[1])

    print(f"Encontrados {len(df_ativos)} tickets ativos.")
    print("Status dos tickets ativos:")
    print(df_ativos['Status'].value_counts())
    
    if df_ativos.empty:
        if os.path.exists(ARQUIVO_ACOMPANHAMENTO): 
            os.remove(ARQUIVO_ACOMPANHAMENTO)
        return

    colunas_acompanhamento = ['Número', 'Data da última ação']
    try:
        df_antigo = pd.read_csv(ARQUIVO_ACOMPANHAMENTO, dtype=str)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_antigo = pd.DataFrame(columns=colunas_acompanhamento)

    for _, ticket_atual in df_ativos.iterrows():
        num_atual = ticket_atual['Número']
        data_atual = ticket_atual['Data da última ação']
        autor_atual = ticket_atual['Autor da Última Ação']
        
        registro_antigo = df_antigo[df_antigo['Número'] == num_atual]

        if registro_antigo.empty or registro_antigo['Data da última ação'].iloc[0] != data_atual:
            if autor_atual not in AUTORES_INTERNOS:
                print(f"[!] RESPOSTA EXTERNA DETECTADA: Ticket #{num_atual} por '{autor_atual}'")
                texto_acao, _ = extrair_ultima_acao_e_autor(ticket_atual['Ações'])
                texto_formatado = formatar_com_ia(texto_acao, GOOGLE_AI_API_KEY)
                info_slack = {
                    'Número': num_atual, 'Assunto': ticket_atual['Assunto'],
                    'Responsável': ticket_atual['Responsável'], 'Ações': texto_formatado,
                    'Autor': autor_atual
                }
                enviar_notificacao_slack(SLACK_WEBHOOK_URL, SLACK_CHANNEL, info_slack)
            else:
                print(f"[-] ATUALIZAÇÃO INTERNA IGNORADA: Ticket #{num_atual} por '{autor_atual}'")

    print(f"\n--- ETAPA 4: ATUALIZANDO ARQUIVO DE ACOMPANHAMENTO ---")
    df_ativos_para_salvar = df_ativos[['Número', 'Data da última ação']]
    df_ativos_para_salvar.to_csv(ARQUIVO_ACOMPANHAMENTO, index=False)
    print(f"'{ARQUIVO_ACOMPANHAMENTO}' atualizado com {len(df_ativos)} tickets ativos.")

def download_relatorio(self):
    """Realiza o download do relatório"""
    try:
        print("Navegando para o download do relatório...")
        self.driver.get("https://app.migrate.com.br/relatorios")
        time.sleep(15)  # Aumentado para 15 segundos
        
        # Tenta encontrar o botão OPÇÕES usando JavaScript
        print("Procurando botão OPÇÕES...")
        opcoes_button = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('OPÇÕES') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not opcoes_button:
            raise Exception("Botão OPÇÕES não encontrado")
        
        print("Botão OPÇÕES encontrado, clicando...")
        self.driver.execute_script("arguments[0].click();", opcoes_button)
        time.sleep(5)
        
        # Tenta encontrar o botão EXPORTAR usando JavaScript
        print("Procurando botão EXPORTAR...")
        exportar_button = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('EXPORTAR') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not exportar_button:
            raise Exception("Botão EXPORTAR não encontrado")
        
        print("Botão EXPORTAR encontrado, clicando...")
        self.driver.execute_script("arguments[0].click();", exportar_button)
        time.sleep(5)
        
        # Tenta encontrar o botão EXCEL usando JavaScript
        print("Procurando botão EXCEL...")
        excel_button = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).find(el => 
                el.textContent.includes('EXCEL') && 
                (el.tagName === 'BUTTON' || el.tagName === 'SPAN' || el.tagName === 'DIV')
            );
        """)
        
        if not excel_button:
            raise Exception("Botão EXCEL não encontrado")
        
        print("Botão EXCEL encontrado, clicando...")
        self.driver.execute_script("arguments[0].click();", excel_button)
        
        # Aguarda o download
        print("Aguardando download do arquivo...")
        time.sleep(30)  # Aumentado para 30 segundos
        
        return True
        
    except TimeoutException as e:
        print(f"Timeout: {str(e)}")
        self.take_screenshot("erro_timeout")
        return False
    except Exception as e:
        print(f"Erro durante o download: {str(e)}")
        self.take_screenshot("erro_download")
        return False

if __name__ == "__main__":
    driver = None
    try:
        if not verificar_variaveis_ambiente():
            raise Exception("Variáveis de ambiente não configuradas.")
            
        driver, download_dir = iniciar_navegador()
        login_e_download(driver, MIGRATE_EMAIL, MIGRATE_SENHA)
        
        df_principal = ler_e_processar_excel(download_dir)
        
        if df_principal is not None:
            analisar_e_notificar_mudancas(df_principal)
        else:
            print("Script encerrado devido a erro na leitura do arquivo Excel.")

    except Exception as e:
        print(f"\n--- ERRO CRÍTICO NA EXECUÇÃO DO SCRIPT: {e} ---")
    finally:
        if driver:
            print("\nFechando o navegador...")
            driver.quit()
        print("Execução finalizada.")
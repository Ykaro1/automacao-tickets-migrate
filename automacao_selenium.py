"""
Script de automação para análise de tickets usando Selenium.
"""

import os
import time
import logging
import pandas as pd
import json
import requests
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    ElementClickInterceptedException
)
from config import config

# Carrega as variáveis de ambiente
load_dotenv()

# Configuração de logging
def setup_logging() -> logging.Logger:
    """Configura o sistema de logging."""
    log_dir = config.paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"automacao_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Log iniciado: {log_file}")
    return logger

# Configurações
class Config:
    """Classe para centralizar configurações."""
    
    def __init__(self):
        self.migrate_email = os.getenv("MIGRATE_EMAIL")
        self.migrate_senha = os.getenv("MIGRATE_SENHA")
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.github_run_id = os.getenv("GITHUB_RUN_ID", "local")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.slack_channel = os.getenv("SLACK_CHANNEL")
        
        # Timeouts
        self.page_load_timeout = 30
        self.element_wait_timeout = 20
        self.download_wait_timeout = 60
        
        # Diretórios
        self.download_dir = Path("downloads").resolve()
        self.screenshot_dir = Path("screenshots").resolve()
        
        # URLs
        self.login_url = "https://atendimento.migrate.com.br/Ticket"
    
    def validate(self) -> bool:
        """Valida se todas as configurações necessárias estão presentes."""
        required_vars = {
            "MIGRATE_EMAIL": self.migrate_email,
            "MIGRATE_SENHA": self.migrate_senha
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            raise ValueError(f"Variáveis de ambiente obrigatórias não configuradas: {missing_vars}")
        
        return True

class TicketAnalyzer:
    """Classe para análise de tickets."""
    
    def __init__(self, file_path):
        self.file_path = file_path
    
    def analyze_tickets(self):
        """Analisa os tickets no arquivo CSV."""
        try:
            # Lista de codificações para tentar
            encodings = ['latin1', 'iso-8859-1', 'cp1252', 'utf-8']
            
            # Tenta cada codificação
            for encoding in encodings:
                try:
                    logging.info(f"Tentando ler arquivo com encoding: {encoding}")
                    
                    # Tenta diferentes configurações de leitura
                    read_options = [
                        {'sep': ',', 'quoting': 1},  # csv.QUOTE_ALL
                        {'sep': ';', 'quoting': 1},  # csv.QUOTE_ALL
                        {'sep': ',', 'quoting': 0},  # csv.QUOTE_MINIMAL
                        {'sep': ';', 'quoting': 0},  # csv.QUOTE_MINIMAL
                    ]
                    
                    for options in read_options:
                        try:
                            df = pd.read_csv(
                                self.file_path,
                                encoding=encoding,
                                sep=options['sep'],
                                quoting=options['quoting'],
                                on_bad_lines='warn'  # Ignora linhas problemáticas
                            )
                            
                            # Se chegou aqui, a leitura foi bem sucedida
                            logging.info(f"Arquivo lido com sucesso usando encoding: {encoding} e opções: {options}")
                            
                            total_tickets = len(df)
                            active_tickets = len(df[df['Status'] == 'Ativo'])
                            
                            status_counts = df['Status'].value_counts()
                            
                            logging.info(f"Total de tickets: {total_tickets}")
                            logging.info(f"Tickets ativos: {active_tickets}")
                            logging.info("\nDistribuição por status:")
                            for status, count in status_counts.items():
                                logging.info(f"{status}: {count}")
                            
                            return True
                            
                        except Exception as e:
                            logging.warning(f"Falha ao ler com opções {options}: {str(e)}")
                            continue
                    
                except UnicodeDecodeError:
                    logging.warning(f"Falha ao ler com encoding {encoding}, tentando próximo...")
                    continue
                except Exception as e:
                    logging.error(f"Erro ao processar arquivo com encoding {encoding}: {str(e)}")
                    continue
            
            raise Exception("Não foi possível ler o arquivo com nenhuma codificação suportada")
            
        except Exception as e:
            logging.error(f"Erro ao analisar tickets: {str(e)}")
            return False

class SeleniumAutomation:
    """Classe principal para automação com Selenium."""
    
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.driver: Optional[webdriver.Chrome] = None
        self.wait = None
        self.analyzer = TicketAnalyzer(self.config.download_dir / "file.csv")
    
    def setup_chrome_options(self) -> Options:
        """Configura as opções do Chrome."""
        chrome_options = Options()
        
        # Configurações básicas
        if not self.config.debug_mode:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Remove indicadores de automação
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Configurações de download
        prefs = {
            "download.default_directory": str(self.config.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 2  # Não carrega imagens para economizar banda
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        return chrome_options
    
    def initialize_driver(self) -> bool:
        """Inicializa o driver do Chrome."""
        try:
            self.logger.info("Inicializando driver Chrome...")
            
            # Cria diretórios necessários
            self.config.download_dir.mkdir(parents=True, exist_ok=True)
            self.config.screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            chrome_options = self.setup_chrome_options()
            
            # Configura o service (opcional, usa o ChromeDriver do PATH)
            service = Service() if not os.path.exists("/usr/local/bin/chromedriver") else Service("/usr/local/bin/chromedriver")
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.config.page_load_timeout)
            
            # Remove propriedades que indicam automação
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, self.config.element_wait_timeout)
            
            self.logger.info("Driver Chrome inicializado com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar driver: {str(e)}")
            return False
    
    def take_screenshot(self, name: str = "screenshot") -> Path:
        """Tira screenshot para debug."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.config.screenshot_dir / f"{name}_{timestamp}.png"
            
            if self.driver:
                self.driver.save_screenshot(str(screenshot_path))
                self.logger.info(f"Screenshot salvo: {screenshot_path}")
            
            return screenshot_path
        except Exception as e:
            self.logger.error(f"Erro ao tirar screenshot: {str(e)}")
            return Path()
    
    def safe_click(self, element, description: str = "elemento") -> bool:
        """Clica em um elemento de forma segura."""
        try:
            # Scroll para o elemento
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            
            # Tenta clicar normalmente
            try:
                element.click()
                self.logger.info(f"Clique realizado em {description}")
                return True
            except ElementClickInterceptedException:
                # Se o clique normal falhar, usa JavaScript
                self.driver.execute_script("arguments[0].click();", element)
                self.logger.info(f"Clique via JavaScript em {description}")
                return True
        
        except Exception as e:
            self.logger.error(f"Erro ao clicar em {description}: {str(e)}")
            return False
    
    def login(self) -> bool:
        """Realiza o login no sistema."""
        try:
            self.logger.info("Iniciando processo de login...")
            
            # Acessa a página de login
            self.driver.get(self.config.login_url)
            self.logger.info(f"Acessando: {self.config.login_url}")
            
            # Aguarda a página carregar
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            time.sleep(3)  # Aguarda estabilização
            
            # Preenche email
            self.logger.info("Preenchendo campo de e-mail...")
            email_input = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[type='email']"))
            )
            email_input.clear()
            time.sleep(0.5)
            email_input.send_keys(self.config.migrate_email)
            self.logger.info("E-mail preenchido")
            
            # Preenche senha
            self.logger.info("Preenchendo campo de senha...")
            password_input = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
            )
            password_input.clear()
            time.sleep(0.5)
            password_input.send_keys(self.config.migrate_senha)
            self.logger.info("Senha preenchida")
            
            # Clica no botão de login
            self.logger.info("Procurando botão de login...")
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button-login, button[type='submit'], input[type='submit']"))
            )
            
            if not self.safe_click(login_button, "botão de login"):
                return False
            
            # Aguarda redirecionamento
            self.logger.info("Aguardando redirecionamento pós-login...")
            time.sleep(5)
            
            # Verifica se há modal de confirmação
            try:
                confirm_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-mv-confirm[data-value='yes']"))
                )
                self.safe_click(confirm_button, "botão de confirmação")
                self.logger.info("Modal de confirmação processado")
            except TimeoutException:
                self.logger.info("Nenhum modal de confirmação encontrado")
            
            # Verifica se o login foi bem-sucedido
            time.sleep(3)
            current_url = self.driver.current_url
            
            if "login" in current_url.lower() or "erro" in current_url.lower():
                self.logger.error("Login pode ter falhado - ainda na página de login")
                self.take_screenshot("login_failed")
                return False
            
            self.logger.info("Login realizado com sucesso")
            return True

        except Exception as e:
            self.logger.error(f"Erro durante login: {str(e)}")
            self.take_screenshot("login_error")
            return False
    
    def export_to_csv(self) -> bool:
        """Exporta os dados para CSV."""
        try:
            self.logger.info("Iniciando processo de exportação...")
            
            # Procura e clica no botão OPÇÕES
            self.logger.info("Procurando botão OPÇÕES...")
            opcoes_selectors = [
                "//span[contains(@class, 'button-text') and text()='OPÇÕES']",
                "//button[contains(text(), 'OPÇÕES')]",
                "//a[contains(text(), 'OPÇÕES')]",
                ".btn-options",
                "#options-button"
            ]
            
            opcoes_button = None
            for selector in opcoes_selectors:
                try:
                    if selector.startswith("//"):
                        opcoes_button = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        opcoes_button = self.wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    break
                except TimeoutException:
                    continue
            
            if not opcoes_button:
                raise Exception("Botão OPÇÕES não encontrado")
            
            if not self.safe_click(opcoes_button, "botão OPÇÕES"):
                return False
            
            time.sleep(2)
            
            # Procura link de exportar para CSV
            self.logger.info("Procurando link de exportação...")
            export_selectors = [
                "a.btnExport.btnExportToCsv",
                "a[href*='csv']",
                "//a[contains(text(), 'CSV')]",
                ".export-csv",
                "#export-csv"
            ]
            
            export_link = None
            for selector in export_selectors:
                try:
                    if selector.startswith("//"):
                        export_link = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        export_link = self.wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    break
                except TimeoutException:
                    continue
            
            if not export_link:
                raise Exception("Link de exportação não encontrado")
            
            if not self.safe_click(export_link, "link de exportação"):
                return False
            
            time.sleep(3)
            
            # Configura opções de exportação se disponível
            try:
                self.logger.info("Configurando opções de exportação...")
                select_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "select.col-xs-12.input-mv-new.md-confirm-options, select[name*='export'], select.export-options"))
                )
                
                select = Select(select_element)
                # Tenta selecionar a opção "Todas as ações na mesma coluna" (valor 3)
                try:
                    select.select_by_value("3")
                    self.logger.info("Opção de exportação configurada")
                except:
                    self.logger.warning("Não foi possível configurar opção específica, usando padrão")
                
                # Clica no botão OK/Confirmar
                ok_selectors = [
                    "button.btn-mv.btn-mv-confirm.md-confirm-action.trigger-service-nps[data-value='ok']",
                    "button[data-value='ok']",
                    "//button[text()='OK']",
                    ".btn-confirm",
                    "#confirm-export"
                ]
                
                ok_button = None
                for selector in ok_selectors:
                    try:
                        if selector.startswith("//"):
                            ok_button = self.wait.until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            ok_button = self.wait.until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        break
                    except TimeoutException:
                        continue
                
                if ok_button:
                    self.safe_click(ok_button, "botão OK")
                
            except TimeoutException:
                self.logger.info("Nenhuma configuração adicional necessária")
            
            self.logger.info("Aguardando download...")
            return self.wait_for_download()
            
        except Exception as e:
            self.logger.error(f"Erro durante exportação: {str(e)}")
            self.take_screenshot("export_error")
            return False
    
    def wait_for_download(self) -> bool:
        """Aguarda o download ser concluído."""
        try:
            start_time = time.time()
            
            while time.time() - start_time < self.config.download_wait_timeout:
                # Verifica arquivos CSV no diretório
                csv_files = list(self.config.download_dir.glob("*.csv"))
                
                if csv_files:
                    # Verifica se o arquivo não está sendo baixado (não tem .crdownload)
                    temp_files = list(self.config.download_dir.glob("*.crdownload"))
                    
                    if not temp_files:
                        # Pega o arquivo mais recente
                        latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
                        
                        # Verifica se o arquivo tem tamanho razoável
                        if latest_file.stat().st_size > 1024:  # Maior que 1KB
                            self.logger.info(f"Download concluído: {latest_file.name} ({latest_file.stat().st_size} bytes)")
                            
                            # Analisa o arquivo
                            if not self.analyzer.analyze_tickets():
                                raise Exception("Falha na análise dos tickets")
                            
                            return True
                
                time.sleep(2)
            
            self.logger.error("Timeout aguardando download")
            return False
            
        except Exception as e:
            self.logger.error(f"Erro aguardando download: {str(e)}")
            return False
    
    def compare_ticket_data(self) -> Tuple[bool, Dict[str, Any]]:
        """Compara os dados dos tickets com a última execução."""
        memory_file = Path("data/ticket_memory.json")
        current_file = self.config.download_dir / "file.xlsx"
        
        try:
            # Verifica se o arquivo atual existe
            if not current_file.exists():
                self.logger.error(f"Arquivo atual não encontrado: {current_file}")
                return False, {}

            # Lê os dados atuais
            try:
                df = pd.read_excel(current_file)
            except Exception as e:
                self.logger.error(f"Erro ao ler arquivo Excel: {str(e)}")
                return False, {}

            current_data = {
                'total_tickets': len(df),
                'tickets_ativos': len(df[df['Status'] == 'Ativo']),
                'data_execucao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status_breakdown': df['Status'].value_counts().to_dict(),
                'hash_arquivo': self._calculate_file_hash(current_file)
            }
            
            # Tenta ler o arquivo de memória do último commit
            try:
                if memory_file.exists():
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        previous_data = json.load(f)
                    
                    # Compara dados incluindo o hash do arquivo
                    has_changes = (
                        current_data['total_tickets'] != previous_data.get('total_tickets', 0) or
                        current_data['tickets_ativos'] != previous_data.get('tickets_ativos', 0) or
                        current_data['status_breakdown'] != previous_data.get('status_breakdown', {}) or
                        current_data['hash_arquivo'] != previous_data.get('hash_arquivo', '')
                    )
                    
                    if has_changes:
                        self.logger.info("Detectadas alterações nos tickets:")
                        if current_data['total_tickets'] != previous_data.get('total_tickets', 0):
                            self.logger.info(f"- Total de tickets alterado: {previous_data.get('total_tickets', 0)} -> {current_data['total_tickets']}")
                        if current_data['tickets_ativos'] != previous_data.get('tickets_ativos', 0):
                            self.logger.info(f"- Tickets ativos alterados: {previous_data.get('tickets_ativos', 0)} -> {current_data['tickets_ativos']}")
                else:
                    self.logger.info("Primeira execução - não há arquivo de memória anterior")
                    has_changes = True  # Primeira execução
                
            # Salva os dados atuais
            memory_file.parent.mkdir(exist_ok=True)
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
            
            return has_changes, current_data
            
        except Exception as e:
            self.logger.error(f"Erro ao comparar dados dos tickets: {str(e)}")
            return False, {}

    def send_to_slack(self, data: Dict[str, Any]) -> bool:
        """Envia atualização para o Slack."""
        if not self.config.app.slack_webhook_url:
            self.logger.warning("Webhook do Slack não configurado")
            return False
        
        try:
            status_text = "\n".join([f"- {status}: {count}" for status, count in data['status_breakdown'].items()])
            
            message = {
                "channel": self.config.app.slack_channel,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔄 Atualização de Tickets Migrate"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Data da execução:* {data['data_execucao']}\n"
                                   f"*Total de tickets:* {data['total_tickets']}\n"
                                   f"*Tickets ativos:* {data['tickets_ativos']}\n\n"
                                   f"*Distribuição por status:*\n{status_text}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Hash do arquivo:* `{data['hash_arquivo']}`"
                    }
                ]
            }
            
            response = requests.post(
                self.config.slack_webhook,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.logger.info("Mensagem enviada com sucesso para o Slack")
                return True
            else:
                self.logger.error(f"Erro ao enviar para Slack: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao enviar para Slack: {str(e)}")
            return False
    
    def commit_changes(self) -> bool:
        """Faz commit das alterações no arquivo de memória e logs."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Comandos git para adicionar e commitar as alterações
            commands = [
                "git add data/ticket_memory.json",
                "git add logs/*",
                f'git commit -m "📊 Atualização de tickets - {timestamp}"'
            ]
            
            for command in commands:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    self.logger.error(f"Erro ao executar '{command}': {result.stderr}")
                    return False
                    
            self.logger.info("Alterações commitadas com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao fazer commit das alterações: {str(e)}")
            return False

    def run(self) -> bool:
        """Executa o processo completo de automação."""
        try:
            # Valida configurações
            self.config.validate()
            
            # Inicializa o driver
            if not self.initialize_driver():
                return False
            
            try:
                # Realiza login
                if not self.login():
                    return False
                
                # Exporta para CSV
                if not self.export_to_csv():
                    return False
                
                # Verifica se houve alterações
                has_changes, current_data = self.compare_ticket_data()
                
                if has_changes:
                    # Envia para o Slack se configurado
                    if self.config.slack_webhook:
                        if not self.send_to_slack(current_data):
                            self.logger.warning("Falha ao enviar notificação para o Slack")
                    
                    # Faz commit das alterações se estiver rodando no GitHub Actions
                    if os.getenv("GITHUB_ACTIONS") == "true":
                        if not self.commit_changes():
                            self.logger.warning("Falha ao fazer commit das alterações")
                else:
                    self.logger.info("Nenhuma alteração detectada nos tickets")
                
                self.logger.info("Processo de automação concluído com sucesso")
                return True
                
            finally:
                # Fecha o driver
                if self.driver:
                    self.driver.quit()
                    self.logger.info("Driver Chrome fechado")
            
        except Exception as e:
            self.logger.error(f"Erro durante execução: {str(e)}")
            self.take_screenshot("error")
            return False

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcula o hash SHA256 do arquivo."""
        import hashlib
        
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Erro ao calcular hash do arquivo: {str(e)}")
            return ""

def main():
    """Função principal."""
    try:
        # Configura logging
        logger = setup_logging()
        logger.info("Iniciando automação...")
        
        # Cria instâncias
        config = Config()
        automation = SeleniumAutomation(config, logger)
        
        # Executa automação
        success = automation.run()
        
        if success:
            logger.info("Automação concluída com sucesso")
            return 0
        else:
            logger.error("Automação falhou")
            return 1

    except Exception as e:
        print(f"Erro fatal: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
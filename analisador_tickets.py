"""
Script para análise de tickets e integração com Gemini e Slack.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import subprocess

# Carrega variáveis de ambiente
load_dotenv()

# Configuração do Gemini
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/analise_tickets.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class TicketAnalyzer:
    def __init__(self):
        self.memory_file = Path("data/ticket_memory.json")
        self.autores_internos = os.getenv("AUTORES_INTERNOS", "").split(",")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.slack_channel = os.getenv("SLACK_CHANNEL")
        
        # Garante que o diretório data existe
        self.memory_file.parent.mkdir(exist_ok=True)
        
        # Carrega ou cria arquivo de memória
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict:
        """Carrega o arquivo de memória ou cria um novo."""
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_memory(self):
        """Salva o arquivo de memória e faz commit no GitHub."""
        # Salva o arquivo
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
        
        # Configura o Git
        try:
            # Configura o usuário do Git
            subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions@github.com'], check=True)
            subprocess.run(['git', 'config', '--global', 'user.name', 'GitHub Actions'], check=True)
            
            # Adiciona o arquivo de memória
            subprocess.run(['git', 'add', str(self.memory_file)], check=True)
            
            # Verifica se há mudanças
            result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
            if result.returncode == 1:  # Há mudanças
                # Faz o commit
                subprocess.run([
                    'git', 'commit', 
                    '-m', f'chore: atualiza memória de tickets - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                ], check=True)
                
                # Faz o push
                subprocess.run(['git', 'push'], check=True)
                logging.info("Memória atualizada e enviada para o GitHub")
            else:
                logging.info("Nenhuma mudança na memória para commitar")
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Erro ao salvar memória no GitHub: {str(e)}")
            # Continua mesmo com erro, pois o arquivo local foi salvo
    
    def _get_last_action(self, actions_text: str) -> Optional[str]:
        """Extrai a última ação do texto de ações."""
        if not actions_text:
            return None
            
        # Divide o texto em ações numeradas
        actions = actions_text.split("-----------------------------")
        
        # Encontra a última ação (maior número)
        last_action = None
        max_number = 0
        
        for action in actions:
            if not action.strip():
                continue
                
            # Procura o número da ação
            try:
                number = int(action.split(" - ")[0].split(" ")[-1])
                if number > max_number:
                    max_number = number
                    last_action = action.strip()
            except (ValueError, IndexError):
                continue
        
        return last_action
    
    def _format_with_gemini(self, text: str) -> str:
        """Formata o texto usando o Gemini."""
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(
                f"Formate o seguinte texto de forma clara e organizada, removendo assinaturas e informações desnecessárias:\n\n{text}"
            )
            return response.text
        except Exception as e:
            logging.error(f"Erro ao formatar com Gemini: {str(e)}")
            return text
    
    def _send_to_slack(self, message: str):
        """Envia mensagem para o Slack."""
        if not self.slack_webhook:
            logging.error("Webhook do Slack não configurado")
            return
            
        try:
            payload = {
                "channel": self.slack_channel,
                "text": message,
                "username": "Monitor de Tickets",
                "icon_emoji": ":ticket:"
            }
            
            response = requests.post(
                self.slack_webhook,
                json=payload
            )
            
            if response.status_code != 200:
                logging.error(f"Erro ao enviar para Slack: {response.text}")
                
        except Exception as e:
            logging.error(f"Erro ao enviar para Slack: {str(e)}")
    
    def _is_internal_author(self, action_text: str) -> bool:
        """Verifica se a ação é de um autor interno."""
        for autor in self.autores_internos:
            if autor.strip() in action_text:
                return True
        return False
    
    def analyze_tickets(self, csv_file: str):
        """Analisa os tickets do arquivo CSV."""
        try:
            # Lê o CSV
            df = pd.read_csv(csv_file, encoding='latin1', sep=';')
            
            # Filtra tickets não fechados/resolvidos
            df = df[~df['Status'].isin(['Fechado', 'Resolvido'])]
            
            for _, ticket in df.iterrows():
                ticket_id = str(ticket['Número'])
                last_action_date = ticket['Data da última ação']
                actions = ticket['Ações']
                
                # Verifica se o ticket já está na memória
                if ticket_id in self.memory:
                    # Verifica se houve alteração na data da última ação
                    if self.memory[ticket_id]['last_action_date'] != last_action_date:
                        # Pega a última ação
                        last_action = self._get_last_action(actions)
                        if last_action:
                            # Verifica se não é autor interno
                            if not self._is_internal_author(last_action):
                                # Formata com Gemini
                                formatted_text = self._format_with_gemini(last_action)
                                
                                # Prepara mensagem para Slack
                                message = (
                                    f"*Novo Ticket #{ticket_id}*\n"
                                    f"*Responsável:* {ticket['Responsável']}\n"
                                    f"*Cliente:* {ticket['Cliente (Pessoa)']}\n"
                                    f"*Status:* {ticket['Status']}\n"
                                    f"*Última Ação:*\n{formatted_text}"
                                )
                                
                                # Envia para Slack
                                self._send_to_slack(message)
                            
                            # Atualiza memória
                            self.memory[ticket_id] = {
                                'last_action_date': last_action_date,
                                'last_action': last_action
                            }
                else:
                    # Novo ticket, adiciona à memória
                    last_action = self._get_last_action(actions)
                    self.memory[ticket_id] = {
                        'last_action_date': last_action_date,
                        'last_action': last_action
                    }
            
            # Salva memória
            self._save_memory()
            
        except Exception as e:
            logging.error(f"Erro ao analisar tickets: {str(e)}")
            raise

def main():
    """Função principal."""
    try:
        analyzer = TicketAnalyzer()
        analyzer.analyze_tickets("downloads/file.csv")
        logging.info("Análise de tickets concluída com sucesso")
        
    except Exception as e:
        logging.error(f"Erro na execução: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
"""
Script para análise de tickets e integração com Gemini e Slack.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
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
        self.slack_channel = os.getenv("SLACK_CHANNEL") # Canal para notificações de tickets
        self.slack_file_update_channel = os.getenv("SLACK_FILE_UPDATE_CHANNEL") # Canal para notificação de atualização do JSON
        
        # Garante que o diretório data existe
        self.memory_file.parent.mkdir(exist_ok=True)
        
        # Carrega ou cria arquivo de memória
        self.memory = self._load_memory()
        logging.info(f"Memória carregada com {len(self.memory)} tickets")
    
    def _load_memory(self) -> Dict[str, Any]:
        """Carrega o arquivo de memória ou cria um novo se não existir."""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Erro ao carregar memória: {str(e)}")
            return {}
    
    def _save_memory(self):
        """Salva o arquivo de memória, faz commit, push e notifica no canal específico sobre a atualização."""
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
            
            # Verifica se há mudanças para commitar
            result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
            if result.returncode == 1:  # Código 1 indica que há mudanças
                # Faz o commit
                commit_message = f'chore: atualiza memória de tickets - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                subprocess.run(['git', 'commit', '-m', commit_message], check=True)
                
                # Faz o push
                subprocess.run(['git', 'push'], check=True)
                logging.info("Memória atualizada e enviada para o GitHub")
                
                # Envia notificação sobre a atualização do arquivo para o canal específico
                repo_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}"
                update_message = f"✅ O arquivo `ticket_memory.json` foi atualizado no repositório.\nConsulte as alterações em: {repo_url}/commits"
                self._send_to_slack(update_message, channel_override=self.slack_file_update_channel)

            else:
                logging.info("Nenhuma mudança na memória para commitar")
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Erro ao salvar memória no GitHub: {str(e)}")
    
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
    
    def _send_to_slack(self, message: str, channel_override: Optional[str] = None):
        """Envia mensagem para o Slack. Permite a sobreposição do canal."""
        if not self.slack_webhook:
            logging.error("Webhook do Slack não configurado")
            return
            
        # Determina o canal de destino: usa o override se fornecido, senão o padrão.
        target_channel = channel_override if channel_override else self.slack_channel
        if not target_channel:
            logging.error("Nenhum canal do Slack especificado para a notificação.")
            return

        try:
            payload = {
                "channel": target_channel,
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
                logging.info(f"Ação é de autor interno: {autor}")
                return True
        return False
    
    def analyze_tickets(self, csv_file: str):
        """
        Analisa os tickets do arquivo CSV com lógica aprimorada para notificações e limpeza de memória.
        """
        try:
            # 1. LER DADOS COMPLETOS
            # Lê o CSV sem filtrar por status para garantir que vejamos as ações de fechamento.
            df = pd.read_csv(
                csv_file,
                encoding='latin1',
                sep=';',
                on_bad_lines='warn',
                engine='python',
                quoting=0,
                dtype={
                    'Número': str,
                    'Status': str,
                    'Ações': str
                }
            )
            logging.info(f"CSV completo lido com {len(df)} tickets")

            # 2. PREPARAR MEMÓRIA
            new_memory = {}
            tickets_com_mudanca = False
            tickets_notificados = 0

            # 3. PROCESSAR CADA TICKET INDIVIDUALMENTE
            for _, ticket in df.iterrows():
                ticket_id = str(ticket['Número'])
                last_action_date = ticket['Data da última ação']
                status = ticket['Status']
                actions = ticket['Ações']
                
                last_action = self._get_last_action(actions)
                if not last_action:
                    continue

                # Lógica de Notificação para tickets existentes
                if ticket_id in self.memory:
                    if self.memory[ticket_id]['last_action_date'] != last_action_date:
                        logging.info(f"Ticket #{ticket_id} (Status: {status}) tem nova ação.")
                        tickets_com_mudanca = True
                        if not self._is_internal_author(last_action):
                            formatted_text = self._format_with_gemini(last_action)
                            message = (
                                f"🔄 *Atualização no Ticket #{ticket_id}*\n"
                                f"*Responsável:* {ticket['Responsável']}\n"
                                f"*Cliente:* {ticket['Cliente (Pessoa)']}\n"
                                f"*Status:* {status}\n"
                                f"*Última Ação:*\n{formatted_text}"
                            )
                            self._send_to_slack(message)
                            tickets_notificados += 1
                # Lógica de Notificação para tickets novos
                elif status not in ['Fechado', 'Resolvido']:
                    logging.info(f"Novo ticket #{ticket_id} encontrado.")
                    tickets_com_mudanca = True
                    if not self._is_internal_author(last_action):
                        formatted_text = self._format_with_gemini(last_action)
                        message = (
                            f"✨ *Novo Ticket #{ticket_id}*\n"
                            f"*Responsável:* {ticket['Responsável']}\n"
                            f"*Cliente:* {ticket['Cliente (Pessoa)']}\n"
                            f"*Status:* {status}\n"
                            f"*Última Ação:*\n{formatted_text}"
                        )
                        self._send_to_slack(message)
                        tickets_notificados += 1

                # 4. LÓGICA DE GESTÃO DA MEMÓRIA
                # Adiciona o ticket na nova memória SOMENTE se ele não estiver fechado/resolvido.
                if status not in ['Fechado', 'Resolvido']:
                    new_memory[ticket_id] = {
                        'last_action_date': last_action_date,
                        'last_action': last_action
                    }

            # 5. ATUALIZAR E SALVAR A MEMÓRIA
            # Verifica se a nova memória é diferente da antiga para evitar commits desnecessários.
            if self.memory != new_memory:
                logging.info("Memória de tickets foi alterada. Salvando novo estado.")
                self.memory = new_memory
                self._save_memory()
            else:
                logging.info("Nenhuma mudança na memória de tickets ativos.")

            # Log final
            logging.info(f"""
            Resumo da análise:
            - Total de tickets processados: {len(df)}
            - Tickets ativos na memória: {len(new_memory)}
            - Tickets com mudança: {tickets_com_mudanca}
            - Tickets notificados: {tickets_notificados}
            """)

            return True

        except Exception as e:
            logging.error(f"Erro ao analisar tickets: {str(e)}")
            return False

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
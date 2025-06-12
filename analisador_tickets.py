"""
Script para análise de tickets e integração com Gemini e Slack.
(Versão com lógica de verificação por número da ação)
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
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
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")  # Principal/Padrão
        self.slack_dynamic_webhook = os.getenv("SLACK_DYNAMIC_WEBHOOK_URL")  # Para notificações de ticket
        self.slack_default_channel = os.getenv("SLACK_CHANNEL")
        self.slack_file_update_channel = os.getenv("SLACK_FILE_UPDATE_CHANNEL")
        self.channel_map = self._load_channel_mapping()
        
        # Garante que o diretório data existe
        self.memory_file.parent.mkdir(exist_ok=True)
        
        # Carrega ou cria arquivo de memória
        self.memory = self._load_memory()
        logging.info(f"Memória carregada com {len(self.memory)} tickets")
    
    def _load_channel_mapping(self) -> Dict[str, str]:
        """Carrega o mapeamento de autores para canais a partir de uma variável de ambiente JSON."""
        mapping_json = os.getenv("SLACK_CHANNEL_MAPPING", "{}")
        try:
            mapping = json.loads(mapping_json)
            logging.info(f"Mapeamento de canais carregado para {len(mapping)} autores.")
            return mapping
        except json.JSONDecodeError:
            logging.error("Erro ao decodificar SLACK_CHANNEL_MAPPING. Verifique o formato JSON.")
            return {}
    
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
            subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions@github.com'], check=True)
            subprocess.run(['git', 'config', '--global', 'user.name', 'GitHub Actions'], check=True)
            subprocess.run(['git', 'add', str(self.memory_file)], check=True)
            
            result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
            if result.returncode == 1:
                commit_message = f'chore: atualiza memória de tickets - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                subprocess.run(['git', 'commit', '-m', commit_message], check=True)
                subprocess.run(['git', 'push'], check=True)
                logging.info("Memória atualizada e enviada para o GitHub")
                
                repo_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}"
                update_message = f"✅ O arquivo `ticket_memory.json` foi atualizado no repositório.\nConsulte as alterações em: {repo_url}/commits"
                self._send_to_slack(update_message, channel_override=self.slack_file_update_channel)
            else:
                logging.info("Nenhuma mudança na memória para commitar")
        except subprocess.CalledProcessError as e:
            logging.error(f"Erro ao salvar memória no GitHub: {str(e)}")
    
    def _get_last_action_details(self, actions_text: str) -> Tuple[int, Optional[str]]:
        """Extrai o número e o texto da última ação."""
        if not actions_text or not isinstance(actions_text, str):
            return 0, None
            
        actions = actions_text.split("-----------------------------")
        last_action_text = None
        max_number = 0
        
        for action in actions:
            if not action.strip():
                continue
            try:
                # Extrai o número da ação. Ex: "1 - Ação..." -> 1
                number_str = action.strip().split(" ")[0]
                number = int(number_str)
                if number > max_number:
                    max_number = number
                    last_action_text = action.strip()
            except (ValueError, IndexError):
                continue
        
        return max_number, last_action_text
    
    def _format_with_gemini(self, text: str) -> str:
        """Formata o texto usando o Gemini."""
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') # Modelo atualizado
            response = model.generate_content(
                f"Resuma e formate o seguinte texto de uma ação de ticket. Remova saudações, assinaturas e informações de rodapé, focando apenas no conteúdo principal da mensagem:\n\n{text}"
            )
            return response.text
        except Exception as e:
            logging.error(f"Erro ao formatar com Gemini: {str(e)}")
            return text
    
    def _send_to_slack(self, message: str, channel_override: Optional[str] = None, use_dynamic_webhook: bool = False):
        """Envia mensagem para o Slack, selecionando o webhook apropriado."""
        if use_dynamic_webhook and self.slack_dynamic_webhook:
            webhook_url = self.slack_dynamic_webhook
            logging.info("Usando webhook dinâmico.")
        else:
            webhook_url = self.slack_webhook
            logging.info("Usando webhook principal.")

        if not webhook_url:
            logging.error("Nenhum webhook do Slack apropriado foi configurado para esta ação.")
            return

        target_channel = channel_override if channel_override else self.slack_default_channel
        if not target_channel:
            logging.error("Nenhum canal do Slack especificado para a notificação.")
            return

        try:
            payload = {"channel": target_channel, "text": message, "username": "Monitor de Tickets", "icon_emoji": ":ticket:"}
            response = requests.post(webhook_url, json=payload)
            if response.status_code != 200:
                logging.error(f"Erro ao enviar para Slack no canal {target_channel}: {response.text}")
        except Exception as e:
            logging.error(f"Erro ao enviar para Slack: {str(e)}")
    
    def _is_internal_author(self, action_text: str) -> bool:
        """Verifica se a ação é de um autor interno."""
        if not action_text: return False
        for autor in self.autores_internos:
            if autor.strip() and autor.strip() in action_text:
                logging.info(f"Ação é de autor interno: {autor}")
                return True
        return False
    
    def analyze_tickets(self, csv_file: str):
        """Analisa os tickets do arquivo CSV com lógica de verificação por número de ação."""
        try:
            df = pd.read_csv(
                csv_file, encoding='latin1', sep=';', on_bad_lines='warn',
                engine='python', quoting=0, dtype={'Número': str, 'Status': str, 'Ações': str, 'Cliente (Pessoa)': str}
            )
            logging.info(f"CSV completo lido com {len(df)} tickets")

            new_memory = {}

            for _, ticket in df.iterrows():
                ticket_id = str(ticket['Número'])
                status = ticket['Status']
                cliente_pessoa = ticket['Cliente (Pessoa)']
                target_channel = self.channel_map.get(cliente_pessoa, self.slack_default_channel)
                
                # Extrai os detalhes da última ação
                last_action_number, last_action = self._get_last_action_details(ticket['Ações'])
                
                if not last_action:
                    continue

                is_active_now = status not in ['Fechado', 'Resolvido']
                
                # Assume que não houve mudança até que se prove o contrário
                has_changed = False
                
                # CASO A: Ticket já monitorado
                if ticket_id in self.memory:
                    previous_action_number = self.memory[ticket_id].get('last_action_number', 0)
                    
                    # NOVA LÓGICA DE VERIFICAÇÃO: O número da ação aumentou?
                    if last_action_number > previous_action_number:
                        has_changed = True
                        was_active_before = self.memory[ticket_id].get('status', '') not in ['Fechado', 'Resolvido']

                        if not self._is_internal_author(last_action):
                            formatted_text = self._format_with_gemini(last_action)
                            
                            if not is_active_now and was_active_before:
                                title = f"✅ *Ticket #{ticket_id} foi Fechado/Resolvido*"
                                logging.info(f"Ticket #{ticket_id} mudou para '{status}'. Notificando canal {target_channel}.")
                            else:
                                title = f"🔄 *Atualização no Ticket #{ticket_id}*"
                                logging.info(f"Ticket #{ticket_id} (Status: {status}) tem nova ação. Notificando canal {target_channel}.")
                            
                            message = f"{title}\n*Responsável:* {ticket['Responsável']}\n*Cliente:* {ticket['Cliente (Pessoa)']}\n*Status:* {status}\n*Última Ação:*\n{formatted_text}"
                            self._send_to_slack(message, channel_override=target_channel, use_dynamic_webhook=True)

                # CASO B: Ticket novo para o sistema
                else:
                    if is_active_now:
                        has_changed = True
                        logging.info(f"Novo ticket ativo #{ticket_id} encontrado. Notificando canal {target_channel}.")
                        
                        if not self._is_internal_author(last_action):
                            formatted_text = self._format_with_gemini(last_action)
                            message = f"✨ *Novo Ticket #{ticket_id}*\n*Responsável:* {ticket['Responsável']}\n*Cliente:* {ticket['Cliente (Pessoa)']}\n*Status:* {status}\n*Última Ação:*\n{formatted_text}"
                            self._send_to_slack(message, channel_override=target_channel, use_dynamic_webhook=True)
                
                # Adiciona à nova memória APENAS se estiver ativo
                if is_active_now:
                    new_memory[ticket_id] = {
                        'last_action_number': last_action_number, # Salva o número da ação
                        'status': status,
                        'last_action': last_action
                    }

            # ATUALIZAÇÃO FINAL DA MEMÓRIA
            if self.memory != new_memory:
                self.memory = new_memory
                self._save_memory()
                logging.info(f"Memória atualizada com {len(new_memory)} tickets ativos")
            else:
                logging.info("Nenhuma mudança estrutural na memória de tickets ativos detectada.")

            return True

        except Exception as e:
            logging.error(f"Erro ao analisar tickets: {str(e)}", exc_info=True)
            return False

def main():
    """Função principal."""
    try:
        analyzer = TicketAnalyzer()
        analyzer.analyze_tickets("downloads/file.csv")
        logging.info("Análise de tickets concluída com sucesso")
    except Exception as e:
        logging.error(f"Erro na execução: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 
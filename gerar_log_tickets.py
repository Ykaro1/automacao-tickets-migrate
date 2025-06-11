"""
Script para gerar log de tickets ativos a partir do arquivo CSV.
"""

import os
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from config import config

def setup_logging():
    """Configura o sistema de logging."""
    log_dir = config.paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"tickets_ativos_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return log_file

def generate_ticket_log():
    """Gera log com informações dos tickets ativos."""
    try:
        # Lista de codificações para tentar
        encodings = ['latin1', 'iso-8859-1', 'cp1252', 'utf-8']
        
        # Tenta cada codificação
        for encoding in encodings:
            try:
                logging.info(f"Tentando ler arquivo com encoding: {encoding}")
                
                # Lê o arquivo CSV
                df = pd.read_csv(
                    config.paths.download_dir / "file.csv",
                    encoding=encoding
                )
                
                # Se chegou aqui, a leitura foi bem sucedida
                logging.info(f"Arquivo lido com sucesso usando encoding: {encoding}")
                
                # Filtra tickets ativos
                tickets_ativos = df[df['Status'] == 'Ativo']
                
                # Gera log
                log_file = config.paths.log_dir / "tickets_ativos.log"
                
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("=== RELATÓRIO DE TICKETS ATIVOS ===\n\n")
                    f.write(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write(f"Total de tickets ativos: {len(tickets_ativos)}\n\n")
                    
                    for _, ticket in tickets_ativos.iterrows():
                        f.write(f"Ticket #{ticket['Número']}\n")
                        f.write(f"Assunto: {ticket['Assunto']}\n")
                        f.write(f"Responsável: {ticket['Responsável']}\n")
                        f.write(f"Data de criação: {ticket['Data de criação']}\n")
                        f.write("-" * 50 + "\n")
                
                logging.info(f"Log gerado com sucesso: {log_file}")
                return True
                
            except UnicodeDecodeError:
                logging.warning(f"Falha ao ler com encoding {encoding}, tentando próximo...")
                continue
            except Exception as e:
                logging.error(f"Erro ao processar arquivo com encoding {encoding}: {str(e)}")
                continue
        
        raise Exception("Não foi possível ler o arquivo com nenhuma codificação suportada")
        
    except Exception as e:
        logging.error(f"Erro ao gerar log: {str(e)}")
        return False

if __name__ == "__main__":
    log_file = setup_logging()
    success = generate_ticket_log()
    exit(0 if success else 1) 
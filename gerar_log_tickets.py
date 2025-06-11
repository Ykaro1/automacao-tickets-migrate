"""
Script para gerar log dos tickets ativos.
"""

import pandas as pd
import sys
from datetime import datetime

def gerar_log_tickets():
    try:
        # Lê o arquivo CSV
        df = pd.read_csv("downloads/file.csv", encoding='utf-8')
        
        # Filtra tickets ativos
        ativos = df[df["Status"] == "Ativo"]
        
        # Gera o log
        with open("logs/tickets_ativos.log", "w", encoding="utf-8") as f:
            f.write("📊 Relatório de Tickets Ativos\n")
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("----------------------------------------\n")
            
            f.write(f"Total de tickets ativos: {len(ativos)}\n")
            f.write("\nDetalhes dos tickets ativos:\n")
            
            for _, ticket in ativos.iterrows():
                f.write(f"\nTicket: {ticket.get('Número', 'N/A')}\n")
                f.write(f"Assunto: {ticket.get('Assunto', 'N/A')}\n")
                f.write(f"Responsável: {ticket.get('Responsável', 'N/A')}\n")
                f.write(f"Data de criação: {ticket.get('Data de criação', 'N/A')}\n")
                f.write("----------------------------------------\n")
        
        print("✅ Log de tickets ativos gerado com sucesso")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao processar arquivo: {str(e)}")
        return False

if __name__ == "__main__":
    if not gerar_log_tickets():
        sys.exit(1) 
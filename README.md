# Automação de Monitoramento de Tickets

Este script automatiza o monitoramento de tickets em um sistema, enviando notificações para o Slack quando houver atualizações.

## Configuração

### Configuração no GitHub Actions

1. Acesse seu repositório no GitHub
2. Vá para Settings > Secrets and variables > Actions
3. Clique em "New repository secret"
4. Adicione cada uma das variáveis necessárias como um secret

### Configuração Local

Para desenvolvimento local, você pode criar um arquivo `.env` na raiz do projeto com as variáveis necessárias.

## Execução

### Localmente

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Execute o script:
```bash
python automacao_selenium.py
```

### No GitHub Actions

O script será executado automaticamente de acordo com o agendamento configurado no arquivo de workflow.

## Segurança

- NUNCA comite credenciais diretamente no código
- Use sempre variáveis de ambiente ou secrets do GitHub
- Mantenha suas chaves de API seguras e não as compartilhe

## Dependências

- Python 3.8+
- Selenium
- pandas
- requests
- google-generativeai

## Licença

Este projeto está sob a licença MIT. 
# Automação de Monitoramento de Tickets

Este script automatiza o monitoramento de tickets em um sistema, enviando notificações para o Slack quando houver atualizações.

## Configuração

### Variáveis de Ambiente Necessárias

O script requer as seguintes variáveis de ambiente para funcionar:

- `MIGRATE_EMAIL`: Email de acesso ao sistema
- `MIGRATE_SENHA`: Senha de acesso ao sistema
- `GOOGLE_AI_API_KEY`: Chave da API do Google AI (Gemini)
- `SLACK_WEBHOOK_URL`: URL do webhook do Slack
- `SLACK_CHANNEL`: ID do canal do Slack

### Configuração no GitHub Actions

1. Acesse seu repositório no GitHub
2. Vá para Settings > Secrets and variables > Actions
3. Clique em "New repository secret"
4. Adicione cada uma das variáveis acima como um secret

### Configuração Local

Para desenvolvimento local, você pode criar um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
MIGRATE_EMAIL=seu_email@exemplo.com
MIGRATE_SENHA=sua_senha
GOOGLE_AI_API_KEY=sua_chave_api
SLACK_WEBHOOK_URL=sua_url_webhook
SLACK_CHANNEL=seu_canal
```

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
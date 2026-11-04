# Segredos e configuracao local

## Regra

Nao armazene chaves em `config.json`, em arquivos de canal ou no codigo. Use `.env` ou variaveis de ambiente do Windows.

1. Copie `.env.example` para `.env`.
2. Preencha as credenciais novas nos campos correspondentes.
3. Nao envie `.env` em ZIPs, capturas ou repositorios.
4. Se uma chave ja foi compartilhada, revogue-a no painel do provedor e gere outra.

Variaveis reconhecidas:

- `GEMINI_API_KEY`
- `PIXABAY_API_KEY`
- `PEXELS_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

A ordem de prioridade e: variaveis ja definidas no Windows > valores do `.env` > configuracoes nao secretas em `config.json`.

`/api/saude` informa apenas se cada credencial esta presente (true/false). Nunca retorna o valor.

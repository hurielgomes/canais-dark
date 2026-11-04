# Atualizacao para Backend v1.2 — interface integrada

## O que mudou
Esta versao atualiza o arquivo que o servidor realmente entrega ao navegador: `ui/index.html`. A rota `/` e a rota `/index.html` servem essa pagina.

Agora a tela tem:
- Seletor de categoria editorial ligado a `/api/categorias`.
- Cartoes dos seis motores visuais ligados a `/api/motores`.
- Estado real: o motor Classico esta ativo; os outros cinco aparecem como `Em desenvolvimento`.
- Motor e categoria enviados a `/api/ideias` e `/api/criar`.
- Motor planejado pode salvar briefing em `/api/projetos`, mas nao entra na fila de renderizacao.
- Abas `Motores` e `Projetos`.
- Aba de motores apresenta as rotas de API para diagnostico.
- `/api/saude` informa a versao `1.2.0-ui-integrada`.

## Instalar com seguranca
1. Feche a Fabrica antiga.
2. Extraia este ZIP completo para uma pasta nova, por exemplo `C:\DarkNetwork\canais-darks-v1.2`. Nao misture arquivos do ZIP antigo e novo.
3. Copie da instalacao antiga apenas os dados que deseja preservar: `canais/`, `modelos/` e `projetos/`. Preserve `canais/<canal>/canal.json`, temas e musicas.
4. Nao substitua o `config.json` sanitizado por um arquivo que contenha chaves antigas. Revogue credenciais que foram compartilhadas e configure chaves novas em `.env` (use `.env.example` como modelo).
5. Entre na pasta `canais-darks` e execute `iniciar.bat`. O inicializador tenta `py app.py`, como no ambiente Windows em que `py` esta disponivel.
6. A pagina aberta precisa ser servida por `http://127.0.0.1:8765/`. Se a aba antiga continuar aberta, faca Ctrl+F5 ou abra o endereco em uma nova janela.
7. Confira o selo `Backend 1.2.0-ui-integrada` no topo.

## Rotas para verificacao
- `http://127.0.0.1:8765/api/saude`
- `http://127.0.0.1:8765/api/motores`
- `http://127.0.0.1:8765/api/categorias`
- `http://127.0.0.1:8765/api/thumbnails`
- `http://127.0.0.1:8765/api/projetos`

## Limites honestos desta entrega
- Somente o motor Classico executa videos reais na fila.
- Broadcast News, Isometric, Blueprint, Stickman e Personagem 2.5D podem ser selecionados e usados para registrar rascunhos, mas ainda nao tem renderizador integrado.
- O motor Classico continua usando um unico roteiro e uma unica duracao para os formatos selecionados. A geracao editorial independente de video longo e Short ainda nao foi implementada.
- O template de thumbnail esta registrado no catalogo; a renderizacao automatica das thumbnails ainda nao foi implementada.

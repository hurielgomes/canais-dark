# Fabrica de Videos — Backend 1.4.0

## O que esta versao entrega

- Preserva o motor Classico e o motor Broadcast News.
- Broadcast News gera roteiros com conhecimento consolidado do Gemini, sem Google Search, grounding ou cota de busca. Assuntos atuais ou mutaveis exigem conferencia manual antes da publicacao.
- Interface `ui/index.html` integrada aos catalogos reais de motores, categorias e thumbnails.
- Categorias com perfis editoriais detalhados: objetivo, tom, estrutura, politica factual, itens a evitar, direcao visual e pergunta final.
- Seletor compacto de motores com icones; motores nao implementados continuam marcados como em desenvolvimento.
- Entregas 16:9 e 9:16 geradas como jobs independentes, com duracoes, roteiros, narracoes e pastas proprias.
- Longo 16:9 configurado para 5–10 min; curto 9:16 para 1–2 min.
- Pergunta final de comentario contextual, adaptada a categoria e ao tom do canal.
- Identidade por canal: nome exibido, logo/marca d'agua, intro opcional e configuracao para logo em miniaturas.
- Fila SQLite persistente, identificacao de interrupcoes e recuperacao de trabalhos.
- Fallback de modelos Gemini apenas para erros de indisponibilidade 5xx/UNAVAILABLE; erros de chave e cota permanecem explicitos.

## Executar

1. Extraia/aplique o patch na pasta que contem `app.py`, `criar_video.py`, `iniciar.bat` e `ui/`.
2. Preserve o `config.json`, `.env`, `iniciar.bat`, `data/fabrica.sqlite3`, canais, projetos, modelos e arquivos gerados.
3. Configure as credenciais locais em `.env` ou `config.json` conforme `docs/SEGREDOS_E_CONFIG.md`.
4. Execute seu `iniciar.bat`. No Windows em que `python app.py` nao foi reconhecido, use `py app.py` dentro do batch.
5. Abra `http://127.0.0.1:8765/` e pressione Ctrl+F5.

## Rotas de diagnostico

- `/api/saude`
- `/api/motores`
- `/api/categorias`
- `/api/thumbnails`
- `/api/projetos`

## Identidade do canal

O nome exibido no topo vem de `canal.json` ou de `identidade.nome_exibicao`. Coloque sua logo em `canais/<slug>/identidade/logo.png` e, se quiser intro, em `canais/<slug>/identidade/intro.mp4`. As opcoes sao documentadas em `docs/BROADCAST_NEWS.md` e no exemplo `canais/exemplo/canal.json`; o patch nao sobrescreve o `canal.json` dos seus canais ativos.

## Motores

- Classico: ativo; imagens/videos de apoio, Kokoro e FFmpeg.
- Broadcast News: ativo; motion graphics jornalisticos locais.
- Isometric, Blueprint, Stickman e Personagem 2.5D: catalogados, mas ainda em desenvolvimento.

Os motores planejados podem receber briefings em `projetos/_planejamento`, mas nao entram na fila de renderizacao ate que o respectivo motor seja implementado e testado.

## Limites factuais

O Broadcast News nao consulta a web nesta versao. Nao publique como atuais leis, aliquotas, cronogramas, cargos, resultados ou numeros recentes sem conferir fontes oficiais. Para conteudos que dependem de atualizacao, o Gemini deve tratar o funcionamento geral e sinalizar verificacao manual.

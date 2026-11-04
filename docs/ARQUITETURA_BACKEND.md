# Backend v1.2 — interface integrada e base para motores visuais

## Objetivo

Preservar o pipeline Classico que ja produz videos e preparar contratos estaveis para adicionar motores sem reescrever fila, projetos, pesquisa, voz ou exportacao.

## Interface v1.2 integrada

O servidor entrega a pagina `ui/index.html` nas rotas `/` e `/index.html`. A tela foi atualizada para consumir os catalogos reais do backend: `/api/motores`, `/api/categorias`, `/api/thumbnails` e `/api/saude`. A interface agora permite selecionar categoria e motor, apresenta o estado ativo/planejado de cada motor, mostra abas de catalogo e projetos, e cria rascunhos para os motores ainda em preparacao.

A geracao de sugestoes tambem recebe a categoria selecionada e adapta as instrucoes editoriais para noticias/economia/politica institucional, engenharia/tecnologia, hipoteticos/humor e esportes.

## O que esta implementado nesta versao

1. **Fila persistente SQLite** em `data/fabrica.sqlite3`.
   - Jobs, estado, progresso, configuracao de producao e ultimas 200 linhas de log ficam persistidos.
   - Jobs que estavam `rodando` quando o servidor foi encerrado sao marcados como `interrompido` no proximo inicio.
   - Jobs `interrompido` nao sao executados automaticamente. A interface oferece **Retomar**.
   - A retomada reaproveita arquivos que `criar_video.py` ja salva por etapa (roteiro, WAVs, imagens e saidas existentes), passando a pasta original por `--projeto`; funciona mesmo se a retomada ocorrer em outro dia.
   - Jobs `pendente` continuam na fila e sao processados pelo worker.

2. **Catalogo de motores** em `motores/catalogo.json`.
   - `classico` esta `active` e continua chamando `criar_video.py`.
   - `broadcast_news`, `isometric`, `blueprint`, `stickman` e `character_2_5d` estao `planned`.
   - Um motor `planned` pode ser usado em um rascunho de projeto, mas nao pode ser enviado para a fila de renderizacao. A API retorna HTTP 409 em vez de simular que ja existe um renderer.

3. **Catalogo de categorias** em `motores/categorias.json`.

4. **Contrato intermediario de projeto** em `schemas/video_project.schema.json`.
   - Suporta entregas independentes, como `youtube_long` 16:9 e `short_vertical` 9:16.
   - Cada entrega tem roteiro e cenas proprios.
   - Cenas podem declarar assets, personagem, acao, emocao, camera, legendas e fontes.
   - O contrato esta pronto para os novos motores; o pipeline Classico ainda nao produz dois roteiros independentes automaticamente.

5. **Especificacao de thumbnail** em `motores/thumbnail_templates.json`, com o layout aprovado e composicoes independentes 16:9/9:16. O renderer de miniaturas novas ainda sera implementado; o pipeline Classico continua usando a miniatura legada.

6. **Rascunhos persistentes** em `projetos/_planejamento/` por meio das rotas `/api/projetos` e `/api/projeto`.

7. **Credenciais fora de `config.json`**.
   - O app le variaveis do ambiente e o arquivo local `.env` (se existir).
   - `.env` nao deve ser compartilhado nem enviado ao Git.

## API local

Base: `http://127.0.0.1:8765`

| Metodo | Rota | Uso |
|---|---|---|
| GET | `/api/saude` | Diagnostico local sem revelar segredos |
| GET | `/api/motores` | Lista motores e estado de implementacao |
| GET | `/api/categorias` | Lista categorias e motores recomendados |
| GET | `/api/thumbnails` | Lista especificacoes de templates de miniatura e formatos |
| GET | `/api/estado` | Canais, conexoes, fila persistente e contagem dos motores |
| GET | `/api/projetos` | Lista rascunhos de projeto |
| GET | `/api/projeto?id=<uuid>` | Le um rascunho |
| POST | `/api/projetos` | Cria rascunho validado |
| POST | `/api/projeto` | Atualiza rascunho existente |
| POST | `/api/criar` | Enfileira producao; aceita `motor` e `categoria`; por enquanto somente `classico` executa |

### Exemplo minimo de criacao de rascunho

```json
{
  "projeto": {
    "schema_version": "1.0",
    "title": "Como funciona uma cidade sustentavel?",
    "channel": "exemplo",
    "category": "como_funciona",
    "engine_id": "isometric",
    "deliverables": {
      "youtube_long": {
        "aspect_ratio": "16:9",
        "target_duration_seconds": 420,
        "script": "",
        "scenes": []
      },
      "short_vertical": {
        "aspect_ratio": "9:16",
        "target_duration_seconds": 90,
        "script": "",
        "scenes": []
      }
    }
  }
}
```

O exemplo cria apenas um rascunho; nao executa um video Isometric, pois esse motor ainda esta planejado.

## Proxima integracao por motor

Cada motor deve implementar um adaptador que recebe o contrato `video_project.json` e produz os assets/planos necessarios. O adaptador nao deve chamar APIs externas diretamente sem passar pela politica de provedores e custo da fabrica.

Sugestao de contrato futuro:

- `validate(project) -> validation_report`
- `build_storyboard(project, deliverable) -> storyboard`
- `render_scene(project, deliverable, scene) -> assets`
- `render_deliverable(project, deliverable) -> output_files`

A interface so deve habilitar um motor quando o adaptador estiver instalado e passar em um teste automatico de renderizacao curta.

## Limites conhecidos

- O Classico continua com um roteiro e uma narracao compartilhados entre os formatos selecionados.
- Os cinco motores novos sao catalogados, mas ainda nao possuem adaptadores de renderizacao.
- A validacao do rascunho e estrutural e inicial; ainda nao substitui validacao integral com JSON Schema.
- A retomada do pipeline Classico reaproveita arquivos existentes, mas nao e uma transacao atomica. O usuario deve revisar o resultado apos retomar.

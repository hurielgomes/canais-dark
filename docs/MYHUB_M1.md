# MyHub Bridge — roteiro e recursos do M1

Esta página resume a integração ampliada. O passo a passo de aplicação está em `INSTALAR_MYHUB_M1.md`.

## Pipeline textual (Clássico/M1)

| Etapa | Opção em `config.json` | Finalidade de chat |
|---|---|---|
| Planejamento narrativo | `provedor_planejamento_narrativa` | `roteiro_planejamento` |
| Criação do roteiro JSON | `provedor_geracao_roteiro` | `roteiro_criacao` |
| Checagem de perguntas | `provedor_refino_roteiro` | `roteiro_checagem` |
| Otimização | `provedor_refino_roteiro` | `roteiro_otimizacao` |
| Refino final | `provedor_refino_roteiro` | `roteiro_refino` |

Cada chave textual aceita `myhub` ou `gemini`. Na interface, as três escolhas são independentes. A checagem, a otimização e o refino final compartilham o seletor de refino, mas usam históricos separados no MyHub.

## Artes do M1

`m1_diretor_padrao` aceita `myhub`, `gemini`, `local` ou `auto`. Com MyHub, o diretor usa chats separados para direção de arte em JSON e geração de recursos SVG/sidecar JSON. Os recursos continuam sendo interpretados, validados e registrados pela biblioteca M1; nenhum código executável é rodado.

A direção de arte mantém fallback para o diretor local/procedural caso a chamada de IA falhe. Já as etapas textuais marcadas como MyHub não mudam silenciosamente para Gemini: a falha é apresentada para diagnóstico.

## Configuração

- `myhub_bridge_dir` ou `MYHUB_BRIDGE_DIR`: caminho da pasta local do Bridge.
- `myhub_timeout_seconds`: timeout de cada chamada textual, em segundos (padrão 900).
- `myhub_model`: opcional; `null` deixa o Bridge usar o modelo ativo/configurado no MyHub.

O adaptador cria jobs em `data/myhub_requests/`, chama `main.py --job <pedido> --yes` e lê `results/<job_id>/response.json` e `response.txt`. O Bridge e a Fábrica devem estar na mesma máquina Windows e o perfil Chromium do Bridge deve estar autenticado.

## Escopo e limites

A seleção de texto aplica-se ao pipeline compartilhado `criar_video.py`, usado pelo motor Clássico e M1. A arte gerada por IA nesta integração corresponde aos recursos vetoriais do M1 (SVG + JSON). A geração de imagens rasterizadas do Clássico continua usando os provedores de imagem já configurados. Os geradores editoriais independentes de `criar_animado.py` e Broadcast News não são alterados nesta versão.

A primeira produção real deve ser testada no Windows do usuário: os testes automatizados utilizam um Bridge simulado e não autenticam nem navegam no MyHub real.

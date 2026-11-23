# PLANO DE INTEGRAÇÃO — M1 (`character_2_5d`)

| # | Etapa | Status | Arquivos principais | Teste |
|---|-------|--------|---------------------|-------|
| 1 | Corrigir `_status` (tupla/exceção de `obter`), separadores `\` do `index.json`, imports `Estilo`/`Tela`, campos da cena (`modelo`, `legenda`) | CONCLUÍDA | `criar_cenas2d.py`, `estudio/.../recursos/biblioteca.py`, `biblioteca_m1/index.json` | execução simulada |
| 2 | Adapter + ativação no catálogo | CONCLUÍDA | `motores/adapters/character_2_5d.py`, `motores/catalogo.json`, `tests/test_backend.py` | `build_command`, `is_engine_executable` |
| 3 | Pipeline simulado 16:9 + 9:16 até MP4 | CONCLUÍDA | `criar_cenas2d.py` | 2 MP4 (1920x1080 e 1080x1920) com áudio; retomada por cache |
| 4 | Diretor de cenas (roteiro → cenas M1 por tags; Gemini opcional com fallback local) | CONCLUÍDA | `diretor_m1.py` | `tests/test_m1_diretor.py` (5 testes) |
| 5 | Compatibilidade com a UI/progresso | CONCLUÍDA (sem alterar `app.py`) | saída `[16x9] plano n/m`; UI lista motores `active` | catálogo/registry |
| 6 | Biblioteca extensível (SVG novo vira recurso sem código) | CONCLUÍDA | `Biblioteca.registrar`, `diretor_m1.py` | SVG `foguete` registrado e usado |
| 7 | Render paralelo por cena (processos) | CONCLUÍDA | `criar_cenas2d.py` (`render_processos` opcional no canal) | execução simulada |
| 8 | **Criação de recursos a partir do roteiro**: direção de arte (Gemini) escolhe recursos da biblioteca e PEDE os que faltam; SVG/JSON criado, validado, testado num quadro de prova, animado (presets) e aprovado; fallback procedural offline | CONCLUÍDA (IA não testada sem rede) | `recursos_ia.py`, `diretor_m1.py` | `tests/test_m1_diretor.py` (8 testes, IA simulada) + vídeo 16:9/9:16 sobre apagão |
| 9 | Validação real (Kokoro + Gemini, 1–2 min) | PENDENTE — precisa do ambiente original | — | rodar pela UI |
| 10 | Regressão dos outros motores | PARCIAL | — | Clássico simulado OK; registry OK |

## Criação de recursos (como funciona)
1. `diretor_m1.py` pede ao Gemini a **direção de arte** por cena: cenário, hero (objeto principal), apoio, personagens, chip e selo; pede **recursos novos** com descrição visual.
2. `recursos_ia.py` pede o SVG (+ JSON de pivôs/animações), valida, testa num quadro e registra/aprova. A IA só enxerga recursos curados/de IA; reservas procedurais ficam ocultas.
3. Sem IA (cota, offline): `recursos_ativos.py` cria soldado articulado, tanque, caça, míssil, navio, bandeira, radar, mapa, explosão, dinheiro, gráfico; e cenários (cidade, interior, natureza, espaço, guerra).
4. `python m1_limpar_biblioteca.py --aplicar` remove reservas procedurais da biblioteca.

## Camada visual didática/viral (nova)
- Composição por cena: hero grande + apoios + personagens, luz de recorte atrás do hero, entrada animada (pop/deslizar), chip "TEMPO · LUGAR", contador numérico animado (0 → valor), selo, chamada com linha-guia (`cena_generica.py`: `contadores`, `chamadas`, `entrada`).
- Kit didático curado (instalado automaticamente): termômetro que sobe, medidor, relógio que passa, barras crescendo/desabando, alvo.
- IA: SVG sem fundo retangular, contorno com gradiente aceito, animações com parte inexistente são podadas (não descartadas).

## Temas visuais (novo)
Prioridade: `canal.json` → `tema_fixo` > tema escolhido pelo Gemini (entre os curados) > padrão da categoria (+ heurística do assunto sem IA).
- Temas: `neon_escuro` (padrão atual), `tensao_quente`, `financas_neutro`, `saude_claro`, `natureza_dia`, `historia_pergaminho`, `educacao_claro`, `pop_claro` (arquivo `temas_m1.py`; categoria → tema em `POR_CATEGORIA`).
- Opcional no `canais/<canal>/canal.json`: `"tema_fixo": "saude_claro"` e `"tema_acento": "#RRGGBB"` (cor da marca; só troca o acento).
- O tema controla: cores do cenário, bloom, vinheta, brilho neon dos objetos, luz de recorte, legenda (cor/sombra), chip, contador, selo e fade. Cenários são específicos do tema (`id__tema`); objetos são reutilizáveis entre temas.
- Contraste da legenda e do acento validado por teste automático (WCAG ≥ 7:1 / 4,5:1).

## MyHub Bridge (novo)
Integrado com o Bridge em `C:/myhub-bridge` (ver `docs/MYHUB_NO_PROJETO.md`): roteiro (planejamento/geração/refino) e direção de arte + SVG do M1 via `myhub_llm.py`;
provedor `auto/myhub/gemini/local` por etapa (UI "Provedores de IA" ou `config.json`); lotes de 2 SVG por mensagem; reparo de JSON; teste de cenário liso.

## Pendências conhecidas
- `editorial_rules.py` não define `INSTRUCAO_FECHAMENTO_PADRAO` (usado por `closing_instruction` e `motores/broadcast_news.py`); quebra `tests/test_backend.py` na importação. Existia no ZIP original, não foi alterado.
- Recursos da biblioteca de exemplo foram marcados como `aprovado`.

## Próximo passo
Etapa 8: rodar um vídeo real de 1–2 min pela UI escolhendo "Personagem ilustrado 2.5D".

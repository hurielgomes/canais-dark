# MyHub Bridge neste projeto

O Bridge continua onde ele já está: **`C:/myhub-bridge`** (a Fábrica NÃO tem cópia dele). Ordem usada para achar a pasta:
variável de ambiente `MYHUB_BRIDGE_DIR` > `config.json` → `myhub_bridge_dir` > `C:/myhub-bridge` (se existir) > `../myhub-bridge`.
Antes de gerar, abra o Bridge (`C:/myhub-bridge`, porta 8766) e deixe a sessão do MyHub logada.

## Onde o MyHub entra
| Etapa | Chave em `config.json` | Valores |
|---|---|---|
| Planejamento narrativo | `provedor_planejamento_narrativa` | `auto` (padrão), `myhub`, `gemini` |
| Geração do roteiro | `provedor_geracao_roteiro` | idem |
| Refino/checagem do roteiro | `provedor_refino_roteiro` | idem |
| M1: direção de arte + SVG/JSON dos recursos | `m1_diretor_padrao` | `auto`, `myhub`, `gemini`, `local` |

`auto` = MyHub se `C:/myhub-bridge` estiver completo (`main.py` + `config.json`); senão Gemini (texto) / Gemini ou local (M1).
Pela interface: seção **Provedores de IA** (grava no `config.json`). Por linha de comando: `python criar_cenas2d.py <canal> "<tema>" --diretor myhub`.
`configurar_provedores_myhub.bat` grava os valores sem abrir a interface; `verificar_chat_scope.bat` confere o isolamento dos chats por projeto.

## Regras de segurança
- Etapa fixada em `myhub` **não** cai em Gemini escondido: se o Bridge falhar, o erro aparece. (No M1, a falha da IA cai no diretor local/procedural, nunca deixa cena vazia.)
- Chats do MyHub são isolados por canal+projeto (`chat_scope`), sem misturar vídeos.
- Nenhuma chave do Gemini é enviada ao MyHub; o Bridge só recebe o prompt.

## M1 via MyHub (resumo)
1. **Direção de arte**: um chat por projeto devolve o JSON (tema, cenário, hero, apoio, personagens, chip, selo, chamada). O JSON é validado e consertado
   (vírgula faltando, cercas ```, cenas faltando → 1 pedido de correção; se ainda falhar, diretor local).
2. **Recursos novos**: objetos e cenários em **lotes de até 2 por mensagem** (arquivos `.svg` anexos, um por recurso); personagens individuais (precisam de pivôs/animações).
   Cada SVG passa pelo validador, por um quadro de prova e (cenários) por um teste de "cenário liso". Rejeitado → 1 tentativa individual → reserva procedural.
3. Tema visual, kit didático, contadores/chamadas e Voicebox funcionam igual com MyHub ou Gemini.

## Não muda
As imagens rasterizadas do motor Clássico (Cloudflare/Gemini/Pixabay) e a voz (Kokoro/Voicebox) continuam como estão.

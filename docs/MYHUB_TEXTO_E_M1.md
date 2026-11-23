# MyHub Bridge — roteiro, refino e artes do M1

## Etapas encaminhadas ao MyHub

| Etapa | Chave no `config.json` | Chat persistente |
|---|---|---|
| Planejamento narrativo | `provedor_planejamento_narrativa` | `fabrica__roteiro_planejamento` |
| Criação do roteiro JSON | `provedor_geracao_roteiro` | `fabrica__roteiro_criacao` |
| Checagem das perguntas | `provedor_refino_roteiro` | `fabrica__roteiro_checagem` |
| Limpeza/otimização | `provedor_refino_roteiro` | `fabrica__roteiro_otimizacao` |
| Refino final | `provedor_refino_roteiro` | `fabrica__roteiro_refino` |
| Direção de arte M1 | `m1_diretor_padrao` | `fabrica_m1__direcao_arte` |
| SVG + sidecar JSON do M1 | `m1_diretor_padrao` | `fabrica_m1__recursos_svg` |

O MyHub é o padrão dessas etapas na versão atualizada. Cada etapa de texto pode
ser trocada de forma independente para `gemini` no `config.json`. Exemplo:

```json
{
  "provedor_planejamento_narrativa": "myhub",
  "provedor_geracao_roteiro": "myhub",
  "provedor_refino_roteiro": "gemini",
  "m1_diretor_padrao": "myhub"
}
```

Essas propriedades devem ser mescladas ao objeto já existente no `config.json`;
não crie um segundo objeto JSON no fim do arquivo. Para ativar os padrões sem
editar o arquivo manualmente, execute `configurar_provedores_myhub.bat` na raiz
da Fábrica. O script cria um backup e preserva o restante da configuração.

## Bridge

Configure `myhub_bridge_dir` (ou a variável `MYHUB_BRIDGE_DIR`) apontando para a
pasta local do Bridge. O Bridge deve ter seu Chromium autenticado. O modelo
selecionado na conversa persistente é reutilizado; para novos chats, a escolha
inicial depende do modelo atualmente ativo no MyHub ou de `myhub_model` no
`config.json` do Bridge.

## Comportamento de falha

- Uma etapa configurada como `myhub` não troca silenciosamente para Gemini.
- Falha na chamada de roteiro aparece como erro identificando MyHub Bridge.
- O planejamento narrativo tem um plano de reserva implementado no núcleo
  editorial; se a resposta do provedor falhar, o núcleo pode prosseguir com esse
  plano de reserva e registrar o aviso.
- A direção de arte M1 conserva o fallback local/procedural já existente.
- O Bridge salva respostas e blocos de código como arquivos; a Fábrica valida
  JSON/SVG e nunca executa Python arbitrário retornado pela IA.

## Escopo

Esta integração cobre o pipeline `criar_video.py` usado pelo motor Clássico e
pelo M1, além da direção de arte e dos recursos SVG/JSON do M1. Os fluxos que
possuem geradores editoriais próprios (por exemplo, `criar_animado.py`) não são
alterados nesta versão.

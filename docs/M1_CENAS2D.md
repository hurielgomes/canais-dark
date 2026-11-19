# Motor Cenas 2D em Camadas (M1) — integração

**ID no catálogo:** `character_2_5d` · **Entrypoint:** `criar_cenas2d.py` · **Adaptador:** `motores/adapters/cenas2d.py` · **Estilo interno:** `cenas2d` (`estudio/estudio/cenas2d/`).
Aparece na interface como **"Cenas 2D em Camadas"** (motor ativo). Formatos: 16:9 e 9:16 (uma entrega por formato, como o Clássico).

## Como funciona

```text
UI / fila (app.py) -> adapters/cenas2d.py -> python criar_cenas2d.py <canal> <tema> --formatos .. --entrega-format ..
  [1/5] Roteiro   Gemini (como o Clássico) ou --simular / --roteiro
  [2/5] Voz       Kokoro (cv.gerar_voz), reaproveita WAVs; invalida por hash se a narração mudou
  [3/5] Cenas     diretor local (kits) OU "cena2d" do roteiro -> cenas2d.json; confere recursos aprovados
  [4/5] Render    1 MP4 sem áudio por cena (processos paralelos, cache por hash) -> concat + áudio + branding
  [5/5] Publicação  miniatura (quadro da cena 1), publicacao.txt, recursos_projeto.json, saida/recursos.html
```
Os marcos de progresso são os mesmos que o `app.py` já lê (`[n/5]`, `Projeto:`, `titulo:`, `voz da cena i/n`, `[fmt] plano i/n`). **Nenhuma alteração em `app.py`, `criar_video.py`, `criar_animado.py`, `engine_*` ou na UI foi necessária.**

## Primeiro uso: recursos aprovados

O motor só usa recursos **aprovados** em `biblioteca_m1/`. Hoje a biblioteca tem 6 recursos de demonstração (tigre, homem, sofá, TV, savana, sala noturna); quem estiver `pendente` faz o job parar com uma mensagem clara. Para aprovar:

```bash
python estudio/m1_recursos.py listar --biblioteca biblioteca_m1
python estudio/m1_recursos.py aprovar tigre --biblioteca biblioteca_m1          # um a um (repita para cada ID)
python criar_cenas2d.py exemplo "Tema" --aprovar-pendentes                        # ou: aprova TODOS os pendentes e segue
python estudio/m1_recursos.py galeria revisao.html --biblioteca biblioteca_m1     # previas visuais para decidir
```
Depois, na interface, use **Retomar** no job que parou.

Teste rápido sem Kokoro/Gemini: `python criar_cenas2d.py exemplo "Tigres em extincao" --simular --formatos 9x16 --fps 8`.

## De onde vem a direção visual de cada cena

1. **`cena2d` no roteiro** (prioridade): uma IA (ou você) pode incluir, em qualquer cena do `roteiro.json`, um objeto `cena2d` no formato do M1 (cenário, elementos, linha do tempo, câmera…). Só pode citar recursos da biblioteca (`"ref"`); `def`/`arquivo` inline são **rejeitados**. Duração e legenda são preenchidas pelo pipeline.
2. **`recursos_novos` no roteiro**: lista de recursos em JSON a registrar na biblioteca. Entram conforme a política `aprovacao_recursos` do `canal.json` (`"manual"` = ficam pendentes até você aprovar — padrão; `"auto"` = já aprovados, para produção em massa) ou `--aprovacao auto|manual`.
3. **Diretor local (kits)** — `biblioteca_m1/kits.json`: modelos de cena (cenário + elementos + animações) com palavras-chave. Cada cena escolhe o kit com mais palavras em comum com a narração, não repete o kit anterior e, sem correspondência, usa um kit "neutro" de ambiente. O tempo do kit é esticado/comprimido para a duração real da fala. Para criar kits novos, copie um existente e troque os `ref`.

## Configuração (opcional, em `canais/<canal>/canal.json`)

| Chave | Padrão | Efeito |
|---|---|---|
| `fps_cenas2d` | 24 | quadros por segundo do render |
| `workers_cenas2d` (ou env `M1_WORKERS`) | metade dos núcleos, máx. 3 | cenas renderizadas em paralelo (cada uma usa ~0,4–0,8 GB) |
| `aprovacao_recursos` | `manual` | política para `recursos_novos` |
| `cenas2d_legenda_maiusculas` | `false` | legenda em caixa alta |
| `legenda_palavras` | (do canal) | palavras por trecho de legenda |

## Desempenho

Medido: ~0,4 s por quadro por núcleo a 1080p (≈ 20 min de CPU para 90 s a 30 fps; a 24 fps ≈ 16 min). Os workers dividem esse tempo por cena. O cache por hash (`segmentos/<fmt>/cena_NN.hash`) evita re-renderizar cenas que não mudaram ao retomar.

## Mensagens comuns

| Mensagem | O que fazer |
|---|---|
| `recursos pendentes de aprovacao: ...` | aprovar (comandos acima) e **Retomar** |
| `nao ha kit utilizavel para as cenas ...` | aprovar os recursos citados ou fornecer `cena2d` no roteiro |
| `recursos inexistentes na biblioteca: X` | `m1_recursos.py registrar <arquivo/pasta>` |
| `aviso: recurso 'X' nao pode ser usado (...)` | o recurso falhou na validação; a cena usa um substituto visível. Veja o motivo no aviso |
| `aviso: 'X' nao tem a animacao 'Y'` | a cena pediu uma animação que o recurso não tem; usa `parado`/pose base |

## Arquivos desta integração

**Novos:** `criar_cenas2d.py` (substitui a tentativa anterior), `motores/adapters/cenas2d.py`, `biblioteca_m1/kits.json`, `estudio/estudio/cenas2d/diretor.py`, `estudio/estudio/cenas2d/segmento.py`, `tests/test_cenas2d_integracao.py`, este documento.
**Alterados:** `motores/catalogo.json` (entrada `character_2_5d`: `planned` → `active`), `tests/test_backend.py` (o motor deixa de ser "não executável"), `estudio/estudio/cenas2d/recursos/biblioteca.py` (caminhos portáveis: índices gerados no Windows com `\` agora funcionam em qualquer sistema; `status_de`, `aprovar_pendentes`), `estudio/estudio/cenas2d/cenas.py` (fades de entrada/saída configuráveis por cena).

## Limitações atuais

- Direção local por kits é simples: com poucos recursos na biblioteca, vídeos de temas distantes dela usam cenas de ambiente. A qualidade cresce com a biblioteca e com a direção visual por IA (`cena2d`), que ainda não é gerada pelo prompt do roteiro.
- Sem sincronização palavra-a-palavra real (legenda proporcional ao tamanho da palavra).
- Recursos hostis/externos não têm isolamento por processo (apenas validação).

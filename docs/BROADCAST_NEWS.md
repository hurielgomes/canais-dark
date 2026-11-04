# Motor Broadcast News — Backend 1.4

## O que faz

Cria explicadores em linguagem jornalistica com cartoes locais de manchete, dados, fluxos, cronologias, comparacoes, graficos, citacoes e listas. Nao exige apresentador fixo nem bancada de jornal.

## Roteiro sem Google Search

O motor usa Gemini sem ferramentas externas ou Google Search. O prompt prioriza conceitos, fatos consolidados e mecanismos estaveis; nao inventa URLs ou fontes consultadas. Leis, aliquotas, calendarios, cargos, resultados e numeros que possam mudar devem ser conferidos manualmente antes da publicacao. Quando um tema depender de atualizacao recente, o roteiro deve explicar o funcionamento geral e incluir uma ressalva de conferencia.

A API Gemini continua necessaria para gerar ideias e roteiro. A ausencia de Google Search significa que nao ha grounding/web search nem fontes atuais automaticamente anexadas.

## Voz, visuais e renderizacao

- Voz: Kokoro ONNX local, compartilhando o pipeline da fabrica.
- Cartoes: Pillow local.
- Animacao, montagem e exportacao: FFmpeg local.
- Identidade: logo d'agua e intro opcional via perfil `identidade` do canal.

## Categorias

Cada categoria e carregada de `motores/categorias.json`, que descreve objetivo, tom, estrutura, politica factual, o que evitar, direcao visual e pergunta final para comentarios. O Broadcast News recebe esse perfil no prompt.

## Formatos independentes

Quando 16:9 e 9:16 estao selecionados na interface, a fila cria dois jobs separados. Cada job recebe duracao, roteiro, narracao, pasta e montagem proprios. A pasta leva sufixo `_16x9` ou `_9x16`, e a interface agrupa as entregas correspondentes na aba Prontos.

- YouTube 16:9: 5 a 10 minutos.
- Shorts/Reels 9:16: 1 a 2 minutos.

## Engajamento

A cena inicial continua sendo um gancho separado. O ultimo trecho deve encerrar com pergunta contextual de comentario, escolhida a partir da categoria e do tom (por exemplo, hipotetico para E se...?, leve para humor e equilibrada para jornalismo).

## Identidade do canal

O perfil `canais/<slug>/canal.json` pode conter:

```json
{
  "identidade": {
    "nome_exibicao": "Nome do canal",
    "logo_arquivo": "identidade/logo.png",
    "marca_dagua": {"ativa": true, "opacidade": 0.22, "posicao": "inferior_direita", "largura_percentual": 10},
    "intro": {"ativa": false, "arquivo": "identidade/intro.mp4"},
    "thumbnail": {"incluir_logo": true, "largura_percentual": 10}
  }
}
```

A logo e a intro sao arquivos fornecidos pelo usuario na pasta do canal. Nao ha logo ou intro criada automaticamente.

## Limites

Esta versao usa motion graphics locais; ainda nao adiciona, por si, imagens de arquivo, mapas detalhados ou video stock jornalistico a cada cena. A thumbnail colorida aprovada esta registrada como template; a identidade/logo pode ser aplicada a miniaturas produzidas pelo pipeline classico. Um renderizador dedicado de thumbnails ainda e uma etapa futura.

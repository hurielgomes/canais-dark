# Voicebox no lugar do Kokoro (opcional, por canal)

## Instalar (Windows)
1. Baixe o instalador do Voicebox na página oficial do projeto (GitHub `jamiepine/voicebox`, botão Windows/MSI) e instale.
2. Abra o Voicebox. Em **Models**, baixe o motor (veja "Qual motor" abaixo). O primeiro download é grande.
3. Crie um **perfil de voz** (ex.: "Narrador"): clone de uma amostra sua/licenciada, ou voz de preset (Qwen CustomVoice).
4. Deixe o Voicebox ABERTO ao gerar vídeos (servidor local em `http://127.0.0.1:17493`). Não exponha essa porta na rede.

## Ligar no canal
Em `canais/<canal>/canal.json` adicione (sem esse bloco, tudo segue no Kokoro):

```json
"tts": {
  "motor": "voicebox",
  "engine": "qwen",
  "perfil": "Narrador",
  "idioma": "pt",
  "velocidade": 1.0,
  "velocidade_gancho": 1.0,
  "fallback_kokoro": true
}
```
Opcionais: `modelo` ("0.6B" ou "1.7B" para qwen), `seed`, `instruct` e `instruct_pergunta` (só o engine `qwen_custom_voice` usa
instrução de entrega, ex.: "tom de pergunta, curioso"), `url`, `exe` (caminho do Voicebox para a Fábrica abri-lo sozinha),
`timeout_s` (padrão 1800), `perfil_id`.
`velocidade` agora é aplicada sem mudar o tom (ffmpeg). O 1,25 do Kokoro costuma ser rápido demais para vozes mais naturais: comece com 1.0–1.1.

## Qual motor
- `qwen` (Qwen3-TTS, clonagem, 10 idiomas incl. português): melhor candidato para naturalidade; sem instrução de tom.
- `qwen_custom_voice`: vozes de preset com instrução de entrega ("pergunta", "mais calmo").
- `chatterbox` (Chatterbox Multilingual, 23 idiomas incl. português): alternativa; tem o parâmetro `exaggeration` no Voicebox.
- `kokoro` dentro do Voicebox NÃO melhora nada: é o mesmo Kokoro.

## Placa AMD (RX 5700) — leia
No Windows, relatos indicam que GPUs AMD caem para CPU no Voicebox (o backend empacotado não traz DirectML; ROCm é Linux-only
e a RX 5700 não é alvo do ROCm). Trate sua máquina como CPU até medir.

## Testar antes de usar
`python voicebox_testar.py <canal>` — checa o servidor, lista perfis, gera 2 frases e imprime a VELOCIDADE
(segundos de processamento por segundo de áudio). Se for muito acima de 1,0, narrações de 1–2 min vão demorar vários minutos só na voz.
Envie a saída completa se algo falhar.

## Comportamento
- Voicebox fechado/erro na 1ª cena: o vídeo inteiro usa Kokoro (voz consistente) e avisa no log.
- Erro no meio do vídeo: para com mensagem clara; as cenas prontas ficam salvas (`audio/NN.wav`). Abra o Voicebox e rode de novo para continuar.
- Vídeos já iniciados com Kokoro mantêm os WAVs antigos; para trocar a voz de um vídeo, apague a pasta `audio` do projeto.

# Estúdio de estilos (versão inicial)

Cria vídeos animados em 2D a partir de um arquivo de roteiro (JSON). Estilos prontos: **telejornal** e **whiteboard**.
Próximos: blueprint, isométrico e palito.

## O que precisa
- Python 3.12 (você já tem) e o FFmpeg (você já tem)
- Uma biblioteca: `python -m pip install pillow`

## Como usar
```
python estudio.py exemplos\telejornal_dolar.json saida.mp4
python estudio.py exemplos\telejornal_dolar.json saida_vertical.mp4 --formato 9x16
python estudio.py exemplos\whiteboard_ceu_azul.json whiteboard.mp4
python estudio.py exemplos\telejornal_dolar.json teste.mp4 --teste 3      (só os 3 primeiros segundos)
```
Cada vídeo de 6 a 11 segundos leva de 20 a 40 segundos para renderizar.

## Como funciona
- `estudio/nucleo.py`: desenho, texto, animação e legenda palavra por palavra.
- `estudio/estilos/`: um arquivo por estilo.
- `exemplos/`: roteiros de exemplo. Um roteiro é uma lista de cenas; cada cena diz o que aparece e quando.

## Créditos
- Estilos inspirados no Lemo-Opuscar (MIT): Broadcast News Package e Whiteboard Explainer.
- Fonte de caneta EMS Tech (SIL OFL 1.1) e fontes DejaVu: veja `estudio/fonts/CREDITOS.txt`.

# Atualização do ProjetoDark (M1 + temas + Voicebox + MyHub Bridge)

Este ZIP traz **só os arquivos novos/alterados**. Ele NÃO contém: `.env`, `config.json`, `canais/`, `projetos/`, `Modelos/` nem `biblioteca_m1/`
(para não sobrescrever suas chaves, canais, vídeos e a biblioteca que já cresceu). Faça um backup da pasta antes e copie por cima.

Arquivos que você pode ter editado à mão e que serão substituídos:
- `criar_video.py` — já inclui o que você usava (função `hifenizar_proparoxitonas` agora em `pronuncia_pt.py`, aplicada só ao texto da voz; requer `pip install pyphen`).
  Se você tinha outras edições nele, reaplique depois.
- `app.py`, `ui/index.html` — seção "Provedores de IA" (MyHub/Gemini/Automático).

Depois de copiar:
1. `pip install -r requirements.txt` (inclui pyphen).
2. Em `config.json`, opcional: copie as chaves de `config.myhub.example.json` (ou rode `configurar_provedores_myhub.bat`).
3. Abra o MyHub Bridge (`C:/myhub-bridge`) antes de gerar. Padrão `auto`: usa MyHub se a pasta existir, senão Gemini.
4. Rode os testes: `python -m unittest tests.test_m1_diretor tests.test_voicebox tests.test_myhub_integracao`.

Guias: `docs/MYHUB_NO_PROJETO.md`, `VOICEBOX.md`, `PLANO_INTEGRACAO_M1.md`.

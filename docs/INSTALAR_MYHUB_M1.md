# Integração MyHub Bridge — roteiro, refino e artes do M1

Este ZIP é um **patch** para a Fábrica de Vídeos. Ele deve ser aplicado sobre a versão que já contém a integração MyHub Bridge/M1 v1. Não é uma cópia completa do projeto.

## O que esta versão conecta

- Planejamento da narrativa no pipeline Clássico/M1.
- Geração do roteiro em JSON no pipeline Clássico/M1.
- Checagem de perguntas sem resposta.
- Otimização e refino do roteiro.
- Direção de arte do M1.
- Geração dos recursos vetoriais do M1: SVG e sidecar JSON.

Os provedores de planejamento, roteiro e refino são selecionáveis independentemente entre MyHub Bridge e Gemini. O provedor de arte do M1 também pode ser MyHub, Gemini, local ou automático.

**Limite de escopo:** esta integração não troca as fontes de imagens rasterizadas do motor Clássico (Cloudflare/Gemini/Pixabay/Pexels), não muda o gerador editorial próprio de `criar_animado.py` e não altera o pipeline independente do Broadcast News. As artes MyHub nesta entrega são as artes vetoriais e os dados estruturados do M1.

## Antes de aplicar

1. Feche a Fábrica.
2. Confirme que o MyHub Bridge v0.2 está instalado e que `testar.bat` consegue enviar e capturar uma resposta.
3. Preserve a pasta `profiles/myhub` do Bridge; ela contém a sessão local do navegador.
4. O patch não contém `config.json`, `.env`, banco SQLite, biblioteca M1 nem vídeos gerados.
5. Se chaves de API antigas foram compartilhadas nos ZIPs anteriores, revogue-as nos serviços e configure novas. Não inclua credenciais em ZIPs.

## Instalação

1. Extraia o conteúdo do ZIP na raiz da Fábrica — a pasta onde ficam `app.py`, `criar_video.py`, `criar_cenas2d.py` e `ui/` — permitindo substituir os arquivos do patch.
2. Não substitua seu `config.json` nem `.env` local.
3. Configure o caminho do Bridge de uma destas formas:
   - no `.env` da Fábrica: `MYHUB_BRIDGE_DIR=C:\\myhub-bridge`; ou
   - no `config.json`: `"myhub_bridge_dir": "C:\\\\myhub-bridge"`.
4. Inicie a Fábrica e abra a seção **Provedores de IA** na área Direção da produção.
5. Selecione MyHub Bridge para Planejamento, Criação do roteiro e Checagem/otimização/refino. Em Direção de arte e SVG/JSON do M1, selecione MyHub Bridge.
6. Clique em **Salvar provedores de IA**. O backend cria `config.json.backup_provedores` e altera apenas essas quatro opções, preservando as demais configurações e chaves.
7. Reinicie a Fábrica para garantir que todos os módulos carreguem a configuração atualizada.

Também é possível executar `configurar_provedores_myhub.bat` na raiz da Fábrica para ativar MyHub nas quatro áreas de uma vez. O script cria um backup com data e hora antes de salvar.

## Configuração equivalente

Os campos são mesclados dentro do objeto JSON existente, nunca como um segundo objeto ao final do arquivo:

```json
{
  "myhub_bridge_dir": "C:\\\\myhub-bridge",
  "provedor_planejamento_narrativa": "myhub",
  "provedor_geracao_roteiro": "myhub",
  "provedor_refino_roteiro": "myhub",
  "m1_diretor_padrao": "myhub",
  "myhub_timeout_seconds": 900,
  "m1_myhub_timeout_seconds": 900,
  "myhub_model": null
}
```

## Conversas persistentes

O adaptador separa conversas por etapa e por projeto/canal. Assim, o planejamento de um vídeo não compartilha o histórico com o roteiro, o refino ou a direção de arte, e produções diferentes também ficam separadas. As chaves usam nomes como `fabrica__roteiro_planejamento__<projeto>` e `fabrica_m1__recursos_svg__<projeto>`.

A Fábrica chama o `main.py` do Bridge com `--job`; o Bridge controla Playwright, reutiliza a URL persistida e salva `response.json`/`response.txt` em `results/<job_id>/`. O adaptador lê a resposta textual. O M1 continua responsável por validar e registrar SVG/JSON na biblioteca.

Com `myhub_model` nulo, o Bridge usa o modelo ativo na interface do MyHub para novos chats, conforme a configuração do Bridge. Se o Bridge não conseguir executar a tarefa, a etapa de roteiro configurada como MyHub informa a falha; não troca silenciosamente para Gemini. A direção de arte M1 mantém seu fallback local/procedural.

## Teste recomendado

1. Confirme que o Bridge continua autenticado. Se necessário, execute `login.bat` e depois `testar.bat` dentro de `C:\\myhub-bridge`.
2. Crie uma produção M1 curta (1–2 minutos) com um tema que exija personagens/objetos novos.
3. No log da Fábrica, confirme mensagens `etapa planejamento: MyHub Bridge`, `etapa roteiro: MyHub Bridge`, `etapa refino: MyHub Bridge`, `MyHub Bridge: enviando direcao_arte` e `MyHub Bridge: enviando recursos_svg`.
4. Verifique `myhub-bridge/results/`, `biblioteca_m1/index.json` e o vídeo renderizado.

## Segurança e diagnóstico

- Não inclua `profiles/myhub/`, `.venv/`, `.env`, cookies ou tokens em ZIPs compartilhados.
- Nenhum código Python retornado pela IA é executado automaticamente.
- Se a Fábrica iniciar, mas mostrar Gemini em alguma etapa, confira o seletor correspondente em **Provedores de IA** e clique em salvar.
- Se aparecer `JSONDecodeError`, valide `config.json` com `py -m json.tool config.json`; o arquivo precisa conter um único objeto JSON.
- A primeira produção real precisa ser validada no Windows onde estão o Bridge autenticado e o Playwright. Os testes locais automatizados não substituem esse teste de ponta a ponta.

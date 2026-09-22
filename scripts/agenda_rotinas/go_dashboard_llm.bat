@echo off
REM ======================================================================
REM  go_dashboard_llm.bat
REM  Substitui go_briefing_llm.bat no 2o slot do Agendador de Tarefas
REM  (06:30, seg-sex, ~15-20 min depois de go_X_briefing_pre.bat). O
REM  Dashboard assume agora o papel de orquestrador nesse horario:
REM    1) Corre X_dashboard_pre.py (mecanico) -- junta contagens/tempo a
REM       partir do _briefing.json ja produzido pela 1a tarefa (06:00) e
REM       decide o pre-filtro needs_action de Artigos/CIRPED/TestMe.
REM    2) Chama o Claude Code em modo nao-interactivo (claude -p) para:
REM       a) interpretar o Briefing (mesmo trabalho que o antigo
REM          go_briefing_llm.bat fazia -- classificar email, escrever
REM          audio_script/alertas/sugestoes -- e publicar via
REM          X_briefing_pos.py + X_hff_pos.py quando Modo A);
REM       b) montar o JSON canonico do Dashboard (date_label, activity
REM          icons da barra do tempo) a partir do output de
REM          X_dashboard_pre.py, e publicar via render.py + Rotina de
REM          Publicacao;
REM       c) accionar TestMe/CIRPED/Artigos SE E SO SE o pre-filtro em (1)
REM          disse que havia algo por fazer -- caso contrario, nao ler
REM          essas rotinas nesta corrida.
REM  A 1a tarefa (go_X_briefing_pre.bat, 06:00) fica inalterada e
REM  independente -- continua a correr sozinha, sem saber que este
REM  ficheiro existe.
REM
REM  Uso manual:
REM     go_dashboard_llm.bat
REM
REM  Uso agendado (Agendador de Tarefas do Windows, 06:30, seg-sex --
REM  reaproveita EXACTAMENTE o slot que antes corria go_briefing_llm.bat):
REM     Programa:   cmd.exe
REM     Argumentos: /c "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\go_dashboard_llm.bat"
REM
REM  NAO tem "pause" de proposito -- uma tarefa agendada nao pode ficar a
REM  espera de uma tecla. A resposta completa do Claude (--output-format
REM  json) fica sempre gravada em _dashboard_llm_log.json.
REM
REM  Permissoes: --permission-mode dontAsk, igual ao go_briefing_llm.bat --
REM  qualquer ferramenta nao pre-autorizada em .claude/settings.json e
REM  NEGADA automaticamente em vez de ficar pendurada a espera de
REM  aprovacao. Antes de confiar nesta tarefa sem vigilancia, confirmar
REM  que .claude/settings.json pre-autoriza tambem "python .../
REM  X_dashboard_pre.py" e "python .../TEMPLATES_DASHBOARD/render.py" (ou
REM  caminho equivalente), alem dos dois comandos X_briefing_pos.py/
REM  X_hff_pos.py ja autorizados.
REM
REM  Modelo fixo (--model claude-sonnet-5), mesma escolha do Rafa para a
REM  tarefa do dia-a-dia (ver go_briefing_llm.bat).
REM
REM  PRIMEIRA CORRIDA: este ficheiro nao foi ainda testado num Windows a
REM  serio -- e novo, escrito na sessao do redesign do Dashboard (22 Set
REM  2026). Testar a mao, de dia, a ver o log completo, antes de o deixar
REM  correr sem vigilancia as 06:30. O ponto mais provavel de precisar de
REM  ajuste: a lista de permissoes em .claude/settings.json (ver nota
REM  acima) e o caminho exacto do X_dashboard_pre.py/render.py passado ao
REM  prompt abaixo.
REM ======================================================================

chcp 65001 >nul
setlocal

set "REPO=C:\Users\rafai\Documents\github\personal-system"
set "AGENDA=G:\My Drive\Claude_PRJ\Agenda"
set "PRE_SCRIPT=%AGENDA%\X_Rotinas_Python\X_dashboard_pre.py"
set "PRE_LOG=%AGENDA%\X_Outputs\_dashboard_pre_log.txt"
set "OUT=%AGENDA%\X_Outputs\_dashboard_llm_log.json"

if not exist "%REPO%" (
    echo ERRO: nao encontrei o checkout do repo em:
    echo   %REPO%
    exit /b 9
)

if not exist "%PRE_SCRIPT%" (
    echo ERRO: nao encontrei a rotina em:
    echo   %PRE_SCRIPT%
    exit /b 9
)

where claude >nul 2>&1
if errorlevel 1 (
    echo ERRO: "claude" nao esta no PATH desta sessao do Agendador de Tarefas.
    exit /b 9
)

REM --- Passo 1: pre mecanico do Dashboard (contagens/tempo/pre-filtro) ---
python "%PRE_SCRIPT%" > "%PRE_LOG%" 2>&1
set "PRE_RC=%ERRORLEVEL%"
type "%PRE_LOG%"
echo.
if not "%PRE_RC%"=="0" (
    echo ERRO: X_dashboard_pre.py terminou com erros. Codigo de saida: %PRE_RC%
    echo Ver detalhe em: %PRE_LOG%
    exit /b %PRE_RC%
)

cd /d "%REPO%"

git fetch origin main >nul 2>&1
git merge --ff-only origin/main >nul 2>&1
if errorlevel 1 (
    echo ERRO: nao consegui sincronizar "%REPO%" com origin/main antes de arrancar.
    echo Ha provavelmente commits locais nao publicados -- resolve no GitHub Desktop
    echo ^(Fetch/Pull origin, depois Push origin^) e volta a correr.
    exit /b 9
)

set "PROMPT=Passo LLM nao-interactivo do Dashboard, disparado pelo Agendador de Tarefas as 06:30 sem ninguem a ver -- nunca pares a pedir confirmacao, publicar e sempre o fim normal desta corrida (regra do Rafa). Este passo substitui o antigo go_briefing_llm.bat: faz o trabalho do Briefing E do Dashboard na mesma corrida. 1) Em G:\My Drive\Claude_PRJ\Agenda\X_Outputs encontra o ficheiro mais recente que termine em _dashboard.json -- e o output que acabou de ser gerado por X_dashboard_pre.py (ja correu antes deste prompt). Le-o na integra: tem counts, weather (3 periodos 08h/16h/20h) e pre_filtro (needs_action de artigos/cirped/testme). 2) BRIEFING: na mesma pasta X_Outputs, encontra o ficheiro mais recente que termine em _briefing.json e NAO termine em _final_briefing.json (produzido pela tarefa separada e independente das 06:00). Se nao encontrares nenhum com menos de 3 horas, para e explica porque, nao inventes nada. Le-o na integra -- e o unico input do Briefing; nunca voltes a consultar Gmail, Calendar, Todoist ou Sheets, ja esta tudo la. Dentro dele, segue a risca o bloco _llm_handoff (lista o que falta fazer e o que nunca fazer). O ponto de partida e canonical_draft: preenche so os campos marcados com comentario LLM (audio_script, alertas, sugestao, conferir, email por categoria, diagnostico.notas_llm se tiveres algo a assinalar) e classifica os emails a partir da chave email na raiz do ficheiro. Nunca inventes dados quando fontes marcar ok=false -- usa um aviso explicito. O JSON final e o canonical_draft preenchido, com exactamente as mesmas chaves de topo (meta, hoje, tarefas, calendario, email, hff, tempo, rotina, diagnostico) -- nao acrescentes nem removas nenhuma. Grava-o na mesma pasta X_Outputs, com o mesmo nome do pre mas trocando o sufixo _briefing.json por _final_briefing.json, usando SEMPRE a ferramenta Write directamente. NUNCA escrevas nem tentes correr nenhum script Python auxiliar ou intermedio para construir ou gravar este ficheiro (nem .tmp_build_*.py nem equivalente) -- esta sessao corre em permission-mode dontAsk e qualquer tentativa de correr python fora dos comandos explicitamente listados abaixo e negada sem hipotese de confirmacao, e trava a corrida com nada publicado. 3) Corre via Bash, a partir da raiz deste repo (C:\Users\rafai\Documents\github\personal-system): python G:/My Drive/Claude_PRJ/Agenda/X_Rotinas_Python/X_briefing_pos.py --json ... --pre-json ..., caminhos entre aspas duplas, sem --dry-run. Se falhar, nao contornes a validacao -- travar aqui e o comportamento correcto. 4) Se o pre.json desta corrida tiver modo.valor igual a A, corre tambem: python G:/My Drive/Claude_PRJ/Agenda/X_Rotinas_Python/X_hff_pos.py --json ... --pre-json ..., mesmos dois caminhos, sem --dry-run -- publica agendas/Hff/index.html e agendas/BO/index.html a partir do bloco hff ja preenchido. Se modo B, salta este passo. 5) DASHBOARD: monta o JSON canonico do modulo dashboard (schema: meta.date_label, counts.events_today, counts.tasks_pending, weather com as chaves 08h/16h/20h, cada uma com icon/temp/activity_icon/activity_title) -- date_label formatado tipo 'Sex, 3 Jul'; counts e weather.icon/weather.temp vem directamente do _dashboard.json lido no passo 1 (nao inventes, nao recalcules); activity_icon/activity_title por periodo e a UNICA parte deste JSON que exige o teu julgamento -- consulta Rafa_profile.md/Feedback_log.json (SSoT) e decide um icone de actividade sugerida (ou null se nao houver nada relevante nesse periodo) seguindo as mesmas regras que sempre usaste aqui. Grava este JSON em X_Outputs com o nome <mesmo timestamp>_final_dashboard.json (ferramenta Write directamente, mesma proibicao de scripts auxiliares do passo 2). Corre: python G:/My Drive/Claude_PRJ/Agenda/Templates/dashboard/render.py <final_dashboard.json> <template.html> <output.html> (descarregar antes template.html e render.py pelos IDs em INSTRUCOES_DASHBOARD Seccao 6 se nao estiverem ja em cache local desta sessao) e depois publica agendas/index.html seguindo a Rotina de Publicacao (commit+push para main, token via github_token.md). 6) PRE-FILTRO: olha para pre_filtro no _dashboard.json do passo 1. Se pre_filtro.artigos.needs_action for true, le INSTRUCOES_ARTIGOS mais recente e segue a rotina Artigos tal como descrita la; se false, nao le nada disso. Mesma logica para pre_filtro.cirped.needs_action com INSTRUCOES_CIRPED.md (Seccao 3) e para pre_filtro.testme.needs_action com TESTME.md -- em qualquer dos tres casos, se needs_action for false, NAO abras o ficheiro de instrucoes desse modulo nesta corrida (e exactamente o que este pre-filtro existe para poupar). Falha em qualquer um destes tres nunca bloqueia os passos anteriores, que ja devem ter publicado o Briefing/HFF/BO/Dashboard. 7) No fim escreve um resumo curto: data-alvo, modo do Briefing, se Briefing/HFF/Dashboard publicaram com sucesso, e o que o pre-filtro decidiu para artigos/cirped/testme (accionado ou poupado)."

claude -p "%PROMPT%" --model claude-sonnet-5 --permission-mode dontAsk --output-format json > "%OUT%" 2>&1
set "RC=%ERRORLEVEL%"

type "%OUT%"
echo.
if "%RC%"=="0" (
    echo [OK] Passo LLM concluido sem erros.
) else (
    echo [ATENCAO] Passo LLM terminou com erros. Codigo de saida: %RC%
    echo Ver detalhe em: %OUT%
)

exit /b %RC%

@echo off
REM ======================================================================
REM  go_briefing_llm.bat
REM  Dispara o passo LLM do Briefing: chama o Claude Code em modo
REM  nao-interactivo (claude -p) para ler o "pre" mais recente
REM  (X_briefing_pre.py), interpreta-lo (classificar email, escrever
REM  audio_scripts/alertas/sugestoes) e publicar via X_briefing_pos.py.
REM  Corre DEPOIS de go_X_briefing_pre.bat ja ter produzido o pre do dia.
REM
REM  Uso manual:
REM     go_briefing_llm.bat
REM
REM  Uso agendado (Agendador de Tarefas do Windows, 06:30, seg-sex,
REM  uns 15-20 min depois de go_X_briefing_pre.bat):
REM     Programa:   cmd.exe
REM     Argumentos: /c "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\go_briefing_llm.bat"
REM
REM  NAO tem "pause" de proposito -- ver go_X_briefing_pre.bat para a
REM  razao (uma tarefa agendada nao pode ficar a espera de uma tecla).
REM  A resposta completa do Claude (--output-format json) fica sempre
REM  gravada em _briefing_llm_log.json, por isso ha sempre rasto mesmo
REM  quando corre sem ninguem a ver.
REM
REM  Permissoes: este passo corre com --permission-mode dontAsk, que
REM  NEGA automaticamente (em vez de ficar pendurado a espera de
REM  aprovacao, que nunca vai vir) qualquer ferramenta que nao esteja
REM  pre-autorizada em .claude/settings.json deste repo. As unicas
REM  pre-autorizacoes la postas sao: ler/escrever ficheiros em
REM  Agenda/X_Outputs e correr "python .../X_briefing_pos.py" (que por
REM  sua vez trata do git add/commit/push por dentro do proprio Python
REM  -- nao precisa de mais nenhuma permissao de Bash para publicar).
REM
REM  Publica sempre: nao ha flag --dry-run aqui de proposito -- se um
REM  dia precisares de ensaiar sem publicar, corre X_briefing_pos.py a
REM  mao com --dry-run (ver o docstring desse ficheiro).
REM
REM  Primeira corrida: testa isto a mao de dia, a ver o log, antes de
REM  confiares nele sem vigilancia as 06:30 -- ao contrario do
REM  go_X_briefing_pre.bat (que ja correu varias vezes contra dados
REM  reais), este ficheiro ainda nao foi testado num Windows a serio;
REM  o ponto mais provavel de precisar de ajuste e a sintaxe exacta das
REM  regras de permissao no settings.json, nao a logica em si.
REM ======================================================================

chcp 65001 >nul
setlocal

set "REPO=C:\Users\rafai\Documents\github\personal-system"
set "OUT=G:\My Drive\Claude_PRJ\Agenda\X_Outputs\_briefing_llm_log.json"
set "PROMPT=Passo LLM nao-interactivo do Briefing Diario, disparado pelo Agendador de Tarefas as 06:30 sem ninguem a ver -- nunca pares a pedir confirmacao, publicar e sempre o fim normal desta corrida (regra do Rafa). 1) Em G:\My Drive\Claude_PRJ\Agenda\X_Outputs encontra o ficheiro mais recente que termine em _briefing.json e NAO termine em _final_briefing.json -- esse e o pre desta corrida. Se nao encontrares nenhum com menos de 3 horas, para e explica porque, nao inventes nada. 2) Le esse ficheiro na integra -- e o unico input; nunca voltes a consultar Gmail, Calendar, Todoist ou Sheets, ja esta tudo la. 3) Dentro dele, segue a risca o bloco _llm_handoff (lista o que falta fazer e o que nunca fazer). O ponto de partida e canonical_draft: preenche so os campos marcados com comentario LLM (audio_script, alertas, sugestao, conferir, email por categoria, diagnostico.notas_llm se tiveres algo a assinalar) e classifica os emails a partir da chave email na raiz do ficheiro. Nunca inventes dados quando fontes marcar ok=false -- usa um aviso explicito. 4) O JSON final e o canonical_draft preenchido, com exactamente as mesmas chaves de topo (meta, hoje, tarefas, calendario, email, hff, tempo, rotina, diagnostico) -- nao acrescentes nem removas nenhuma, e nao copies mais nada do resto do ficheiro do pre. Grava-o na mesma pasta X_Outputs, com o mesmo nome do pre mas trocando o sufixo _briefing.json por _final_briefing.json. 5) Corre via Bash, a partir da raiz deste repo (C:\Users\rafai\Documents\github\personal-system): python G:/My Drive/Claude_PRJ/Agenda/X_Rotinas_Python/X_briefing_pos.py --json ... --pre-json ..., com o caminho do script e os dois caminhos --json/--pre-json sempre entre aspas duplas (nunca aspas simples) e os caminhos completos dos dois ficheiros desta corrida -- sem --dry-run, a publicacao e sempre o objectivo. Se esse comando falhar, nao tentes contornar a validacao nem publicar por outra via -- e suposto travar aqui mesmo que isso aconteca. 6) No fim escreve um resumo curto: data-alvo, modo, se publicou com sucesso, e quantos avisos/erros ficaram na aba Diagnostico."

if not exist "%REPO%" (
    echo ERRO: nao encontrei o checkout do repo em:
    echo   %REPO%
    exit /b 9
)

where claude >nul 2>&1
if errorlevel 1 (
    echo ERRO: "claude" nao esta no PATH desta sessao do Agendador de Tarefas.
    exit /b 9
)

cd /d "%REPO%"

claude -p "%PROMPT%" --permission-mode dontAsk --output-format json > "%OUT%" 2>&1
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

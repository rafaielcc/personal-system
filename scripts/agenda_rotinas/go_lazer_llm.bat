@echo off
REM ======================================================================
REM  go_lazer_llm.bat
REM  Passo periodico LLM da Agenda de Lazer. A periodicidade fica a cargo
REM  do Agendador de Tarefas. A publicacao e SEMPRE automatica depois de:
REM    1) pre mecanico fresco e sem erros;
REM    2) JSON final escrito directamente pela LLM;
REM    3) postflight sem publicacao concluido com sucesso.
REM
REM  Nao pede confirmacao ao Rafa. Uma falha aborta e fica no log.
REM ======================================================================

chcp 65001 >nul
setlocal EnableExtensions

set "REPO=C:\Users\rafai\Documents\github\personal-system"
set "AGENDA=G:\My Drive\Claude_PRJ\Agenda"
set "PRE_SCRIPT=%AGENDA%\X_Rotinas_Python\X_lazer_pre.py"
set "POST_SCRIPT=%AGENDA%\X_Rotinas_Python\Agenda_Lazer\postflight_lazer.py"
set "OUT_DIR=%AGENDA%\X_Outputs\lazer"
set "LATEST_PRE=%OUT_DIR%\_latest_lazer_pre.txt"
set "LATEST_FINAL=%OUT_DIR%\_latest_lazer_final.txt"
set "PRE_LOG=%OUT_DIR%\_lazer_pre_before_llm_log.txt"
set "LLM_LOG=%OUT_DIR%\_lazer_llm_log.json"
set "POST_LOG=%OUT_DIR%\_lazer_postflight_log.txt"
set "PUBLISH_LOG=%OUT_DIR%\_lazer_publish_log.txt"

if not exist "%REPO%\.git" (
    echo ERRO: checkout Git nao encontrado em "%REPO%".
    exit /b 9
)
if not exist "%PRE_SCRIPT%" (
    echo ERRO: X_lazer_pre.py nao encontrado em "%PRE_SCRIPT%".
    exit /b 9
)
if not exist "%POST_SCRIPT%" (
    echo ERRO: postflight_lazer.py nao encontrado em "%POST_SCRIPT%".
    exit /b 9
)
where claude >nul 2>&1
if errorlevel 1 (
    echo ERRO: "claude" nao esta no PATH desta sessao.
    exit /b 9
)
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

REM Garante um handoff fresco. Se o pre diario tiver menos de 30 horas,
REM apenas o reutiliza; caso contrario faz uma recolha completa agora.
python "%PRE_SCRIPT%" --ensure-fresh-hours 30 --refresh-mode all > "%PRE_LOG%" 2>&1
set "PRE_RC=%ERRORLEVEL%"
type "%PRE_LOG%"
echo.
if not "%PRE_RC%"=="0" (
    echo ERRO: pre mecanico bloqueou a corrida LLM. Codigo: %PRE_RC%
    exit /b %PRE_RC%
)

if not exist "%LATEST_PRE%" (
    echo ERRO: ponteiro do pre nao foi criado: "%LATEST_PRE%".
    exit /b 8
)
if not exist "%LATEST_FINAL%" (
    echo ERRO: ponteiro do final nao foi criado: "%LATEST_FINAL%".
    exit /b 8
)
set /p "PRE_PATH="<"%LATEST_PRE%"
set /p "FINAL_PATH="<"%LATEST_FINAL%"
if not exist "%PRE_PATH%" (
    echo ERRO: pre apontado nao existe: "%PRE_PATH%".
    exit /b 8
)

REM Evita que um final antigo da mesma recolha seja publicado se a LLM
REM terminar sem escrever o ficheiro novo.
if exist "%FINAL_PATH%" move /y "%FINAL_PATH%" "%FINAL_PATH%.before_llm.bak" >nul

cd /d "%REPO%"
set "BRANCH="
for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if /I not "%BRANCH%"=="main" (
    echo ERRO: publicacao recusada fora do branch main. Branch actual: %BRANCH%
    exit /b 9
)
git fetch origin main >nul 2>&1
git merge --ff-only origin/main >nul 2>&1
if errorlevel 1 (
    echo ERRO: nao consegui sincronizar o repo com origin/main.
    exit /b 9
)

set "PROMPT=Passo LLM nao-interactivo da Agenda de Lazer. A publicacao ao final e sempre autorizada pelo Rafa, sem pedir confirmacao; quem publica e o launcher depois de validares o JSON. 1) Le integralmente e apenas o ficheiro %PRE_PATH%. Ele e a unica fonte desta corrida. Nao consultes web, Gmail, Calendar, Sheets, Drive, Todoist nem outros ficheiros. 2) Segue exactamente o bloco _llm_handoff. Parte de canonical_draft e altera apenas os caminhos listados em editable_paths. Perfil, feedback, viagens, tempo, calendario, curadoria, candidatos e falhas de fonte ja estao todos dentro do JSON. 3) Constroi events[] apenas a partir de event_candidates[], usando julgamento para seleccao, ranking, highlights, redaccao, badges e with_tags. Nunca inventes datas, sessoes, canais, precos, links ou disponibilidade. Uma fonte com ok=false continua como lacuna explicita. Nunca uses eventos apenas provaveis para preencher thresholds. 4) O JSON final tem exactamente as chaves de topo meta, sources, event_candidates, events, futuro_guardado, summary e validation. Nao acrescentes nem removas chaves de topo e nao copies _llm_handoff. 5) Grava o JSON final directamente em %FINAL_PATH% usando sempre a ferramenta Write. NUNCA cries nem executes script Python auxiliar, .tmp_build_*.py ou equivalente; esta sessao corre em permission-mode dontAsk. 6) Nao escrevas HTML, nao corras render/postflight, nao facas commit nem push. O launcher fara validacao, render e publicacao automaticamente quando terminares. No fim responde apenas com um resumo curto da curadoria e das lacunas documentadas."

claude -p "%PROMPT%" --model claude-sonnet-5 --permission-mode dontAsk --output-format json > "%LLM_LOG%" 2>&1
set "LLM_RC=%ERRORLEVEL%"
type "%LLM_LOG%"
echo.
if not "%LLM_RC%"=="0" (
    echo ERRO: passo LLM terminou com codigo %LLM_RC%.
    exit /b %LLM_RC%
)
if not exist "%FINAL_PATH%" (
    echo ERRO: a LLM terminou sem criar o JSON final esperado:
    echo   %FINAL_PATH%
    exit /b 7
)

REM Primeira passagem obrigatoriamente sem publicacao.
python "%POST_SCRIPT%" --json "%FINAL_PATH%" --repo "%REPO%" > "%POST_LOG%" 2>&1
set "POST_RC=%ERRORLEVEL%"
type "%POST_LOG%"
echo.
if not "%POST_RC%"=="0" (
    echo ERRO: postflight de validacao/render bloqueou a publicacao.
    exit /b %POST_RC%
)

REM Publicacao sempre automatica, autorizada permanentemente pelo Rafa.
python "%POST_SCRIPT%" --json "%FINAL_PATH%" --repo "%REPO%" --publish > "%PUBLISH_LOG%" 2>&1
set "PUB_RC=%ERRORLEVEL%"
type "%PUBLISH_LOG%"
echo.
if "%PUB_RC%"=="0" (
    echo [OK] Agenda de Lazer validada, renderizada e publicada.
) else (
    echo [ERRO] Publicacao terminou com codigo %PUB_RC%.
)

exit /b %PUB_RC%

@echo off
REM ======================================================================
REM  go_X_lazer_pre.bat
REM  Tarefa mecanica diaria da Agenda de Lazer. Nao chama LLM e nao
REM  publica. X_lazer_pre.py incorpora as quatro extraccoes do antigo
REM  Go_All_events.bat, recolhe as restantes fontes e gera o handoff.
REM
REM  Agendador de Tarefas (diariamente as 03:30):
REM    Programa:   cmd.exe
REM    Argumentos: /c "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\go_X_lazer_pre.bat"
REM ======================================================================

chcp 65001 >nul
setlocal

set "AGENDA=G:\My Drive\Claude_PRJ\Agenda"
set "PRE_SCRIPT=%AGENDA%\X_Rotinas_Python\X_lazer_pre.py"
set "LOG=%AGENDA%\X_Outputs\lazer\_lazer_pre_log.txt"

if not exist "%PRE_SCRIPT%" (
    echo ERRO: nao encontrei a rotina em:
    echo   %PRE_SCRIPT%
    exit /b 9
)

if not exist "%AGENDA%\X_Outputs\lazer" mkdir "%AGENDA%\X_Outputs\lazer"

python "%PRE_SCRIPT%" --refresh-mode all > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

type "%LOG%"
echo.
if "%RC%"=="0" (
    echo [OK] Pre mecanico da Agenda de Lazer concluido.
) else (
    echo [ERRO] Pre mecanico terminou com codigo %RC%.
    echo Ver detalhe em: %LOG%
)

exit /b %RC%

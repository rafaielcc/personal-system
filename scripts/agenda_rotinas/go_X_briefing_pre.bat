@echo off
REM ======================================================================
REM  go_X_briefing_pre.bat
REM  Dispara a recolha mecanica do Briefing (X_briefing_pre.py).
REM
REM  Uso manual:
REM     go_X_briefing_pre.bat                  (modo automatico)
REM     go_X_briefing_pre.bat --mode B
REM     go_X_briefing_pre.bat --next-business-day
REM     go_X_briefing_pre.bat --today
REM     go_X_briefing_pre.bat --self-test
REM
REM  Uso agendado (Agendador de Tarefas do Windows, 06:00, seg-sex):
REM     Programa:   cmd.exe
REM     Argumentos: /c "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\go_X_briefing_pre.bat"
REM
REM  NAO tem "pause" de proposito: um pause faria a tarefa agendada ficar
REM  pendurada para sempre a espera de uma tecla que ninguem vai carregar.
REM  A consola e sempre gravada em _briefing_pre_log.txt, por isso ha
REM  sempre rasto mesmo quando corre sem ninguem a ver.
REM ======================================================================

chcp 65001 >nul
setlocal

set "PRE=G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\X_briefing_pre.py"
set "OUT=G:\My Drive\Claude_PRJ\Agenda\X_Outputs\_briefing_pre_log.txt"

if not exist "%PRE%" (
    echo ERRO: nao encontrei a rotina em:
    echo   %PRE%
    exit /b 9
)

python "%PRE%" %* > "%OUT%" 2>&1
set "RC=%ERRORLEVEL%"

type "%OUT%"
echo.
if "%RC%"=="0" (
    echo [OK] Pre concluido sem erros.
) else (
    echo [ATENCAO] Pre terminou com erros. Codigo de saida: %RC%
    echo Ver detalhe em: %OUT%
)

exit /b %RC%

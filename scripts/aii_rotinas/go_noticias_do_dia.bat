@echo off
REM ======================================================================
REM  go_noticias_do_dia.bat
REM  Dispara a rotina "Noticias do Dia" (projeto AII) via Claude Code em
REM  modo nao-interactivo (claude -p), invocando directamente o skill
REM  /noticias-do-dia. Ao contrario do Briefing/Painel HFF, esta rotina
REM  nao tem um "pre" Python separado disparado pelo .bat: o preflight
REM  proprio da rotina (AII_X_preflight_noticias_do_dia.py) e chamado
REM  pelo proprio Claude, como parte da Etapa 0.0B da rotina.
REM
REM  Uso manual:
REM     go_noticias_do_dia.bat
REM
REM  Uso agendado (Agendador de Tarefas do Windows, 15:00, seg-sex):
REM     Programa:   cmd.exe
REM     Argumentos: /c "G:\My Drive\Claude_PRJ\AIIB3\Obsidian\go_noticias_do_dia.bat"
REM
REM  Permissoes: ao contrario do Briefing/HFF, esta rotina usa muitas
REM  mais ferramentas (Drive, pesquisa web em varias fontes, Sheets) e
REM  esta em evolucao activa (v5.21+) -- nao compensa manter uma lista
REM  fixa de autorizacoes em .claude/settings.json, que ficaria
REM  desactualizada a cada fonte nova. Por decisao explicita do Rafa,
REM  este passo corre com --permission-mode bypassPermissions: acesso
REM  total, sem pedir nada, tal como quando a rotina corre interactiva
REM  e o Rafa vai aprovando tudo. Sem rede de seguranca nesta janela --
REM  se um dia for preciso mais controlo, mudar para dontAsk e construir
REM  a lista de permissoes equivalente.
REM
REM  Correccao embutida no PROMPT: a rotina, no caminho "ambiente local",
REM  assume por omissao o checkout G:\My Drive\Claude_PRJ\personal-system
REM  para o git commit/push da Etapa 4B -- mas esse checkout (dentro da
REM  pasta sincronizada do Drive) tem o git corrompido pela propria
REM  sincronizacao (erro confirmado: "fatal: git show-ref: bad ref
REM  refs/tags/desktop.ini"), o mesmo problema ja resolvido para o
REM  Briefing/HFF ao mover a publicacao para um checkout fora do Drive.
REM  Por isso o PROMPT abaixo instrui sempre a passar
REM  --repo "C:\Users\rafai\Documents\github\personal-system" ao
REM  AII_X_postflight_noticias_do_dia.py, em vez do valor por omissao.
REM
REM  A resposta completa do Claude (--output-format json) fica sempre
REM  gravada em _noticias_llm_log.json, por isso ha sempre rasto mesmo
REM  quando corre sem ninguem a ver.
REM
REM  Modelo fixo (--model claude-opus-5): sem isto, a corrida usaria o
REM  que estiver definido por omissao nesta instalacao do Claude Code --
REM  podia mudar sem aviso se o modelo por omissao for trocado noutro
REM  contexto. Opus 5 por escolha do Rafa (mais julgamento exigido:
REM  relevancia para a carteira, sintese de varias fontes).
REM
REM  Primeira corrida: testa isto a mao, a ver o log, antes de confiares
REM  nele sem vigilancia as 15:00 -- nunca foi corrido num Windows real
REM  a partir do Agendador de Tarefas.
REM
REM  Sincronizacao automatica com origin/main: sessoes de Claude Code na
REM  cloud podem publicar directamente em main a qualquer momento -- se
REM  este checkout local ficar para tras, o proprio postflight desta
REM  rotina pode falhar no git push por divergencia (mesmo problema
REM  confirmado no Briefing em 2026-09-18). Por isso sincronizamos
REM  sempre primeiro, com --ff-only (nunca cria merge commit sozinho; se
REM  nao conseguir avancar de forma linear, para e reporta).
REM ======================================================================

chcp 65001 >nul
setlocal

set "REPO=C:\Users\rafai\Documents\github\personal-system"
set "OUT=G:\My Drive\Claude_PRJ\AIIB3\Obsidian\_noticias_llm_log.json"
set "PROMPT=Passo nao-interactivo da rotina Noticias do Dia, disparado pelo Agendador de Tarefas as 15:00 sem ninguem a ver -- nunca pares a pedir confirmacao, publicar e sempre o fim normal desta corrida (regra do Rafa). Executa agora a rotina /noticias-do-dia, em ativacao DIRECTA, ambiente LOCAL (este e o PC do Rafa, com o Drive sincronizado em G:) -- segue sempre os caminhos e o metodo 'ambiente local' descritos na rotina, nunca os de ambiente cloud. Modalidade por omissao (FULL com fontes + pagina HTML), salvo se a propria rotina disser o contrario. CORRECCAO OBRIGATORIA para a Etapa 4B (publicacao): quando correres o AII_X_postflight_noticias_do_dia.py, mesmo que o exemplo 'ambiente local' da rotina nao mostre o parametro --repo, inclui sempre explicitamente --repo \"C:\Users\rafai\Documents\github\personal-system\" -- NUNCA deixes o script usar o checkout por omissao dentro da pasta do Drive (G:\My Drive\Claude_PRJ\personal-system), porque esse checkout tem o git corrompido pela sincronizacao do proprio Drive (erro conhecido: fatal: git show-ref: bad ref refs/tags/desktop.ini). Se o script nao aceitar --repo nesse contexto ou falhar mesmo assim, para e relata o erro exacto, nao tentes contornar publicando por outra via. No fim escreve um resumo curto: se a rotina completou, se gerou e publicou o HTML (agendas/noticiasB3/index.html), e quaisquer avisos/desvios assinalados nos METADADOS do relatorio."

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

git fetch origin main >nul 2>&1
git merge --ff-only origin/main >nul 2>&1
if errorlevel 1 (
    echo ERRO: nao consegui sincronizar "%REPO%" com origin/main antes de arrancar.
    echo Ha provavelmente commits locais nao publicados -- resolve no GitHub Desktop
    echo ^(Fetch/Pull origin, depois Push origin^) e volta a correr.
    exit /b 9
)

claude -p "%PROMPT%" --model claude-opus-5 --permission-mode bypassPermissions --output-format json > "%OUT%" 2>&1
set "RC=%ERRORLEVEL%"

type "%OUT%"
echo.
if "%RC%"=="0" (
    echo [OK] Noticias do Dia concluida sem erros.
) else (
    echo [ATENCAO] Noticias do Dia terminou com erros. Codigo de saida: %RC%
    echo Ver detalhe em: %OUT%
)

exit /b %RC%

@echo off
REM ======================================================================
REM  go_notificacoes.bat
REM  Dispara a rotina de Notificacoes (triagem WhatsApp via MacroDroid/
REM  Espelho_Notificacoes) via Claude Code em modo nao-interactivo
REM  (claude -p), invocando directamente o skill /notificacoes. Ao
REM  contrario do Briefing/Painel HFF, esta rotina nao tem um ".bat de
REM  pre" separado: o preflight proprio da rotina
REM  (preflight_notificacoes.py) e chamado pelo proprio Claude, como
REM  primeiro passo, tal como ja acontece no go_noticias_do_dia.bat (AII).
REM
REM  Uso manual:
REM     go_notificacoes.bat
REM
REM  Uso agendado (Agendador de Tarefas do Windows -- sem hora fixa
REM  definida de proposito; o Rafa escolhe a hora ao criar a tarefa):
REM     Programa:   cmd.exe
REM     Argumentos: /c "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\go_notificacoes.bat"
REM
REM  Permissoes: tal como a Noticias do Dia (nao o Briefing), esta rotina
REM  usa uma superficie de ferramentas larga e imprevisivel num unico
REM  ciclo -- preflight Python com autenticacao Google Sheets, render
REM  Python, e depois comandos git raw (add/commit/push) escritos na
REM  propria instrucoes_notificacoes.md, em vez de um unico script "pos"
REM  como o X_briefing_pos.py. Nao compensa manter uma lista fixa de
REM  autorizacoes em .claude/settings.json para isto. Por isso corre com
REM  --permission-mode bypassPermissions: acesso total, sem pedir nada --
REM  mesmo criterio e mesmo risco aceite do go_noticias_do_dia.bat. Sem
REM  rede de seguranca nesta janela -- se um dia for preciso mais
REM  controlo, mudar para dontAsk e construir a lista de permissoes
REM  equivalente (script a script).
REM
REM  Correccao embutida no PROMPT: a Seccao 6 (Renderizacao) e a Seccao 7
REM  (Publicacao) de instrucoes_notificacoes.md escrevem literalmente
REM  para/a partir de "G:\My Drive\Claude_PRJ\personal-system" -- mas esse
REM  checkout (dentro da pasta sincronizada do Drive) tem o git corrompido
REM  pela propria sincronizacao (erro confirmado: "fatal: git show-ref:
REM  bad ref refs/tags/desktop.ini"), o mesmo problema ja resolvido para o
REM  Briefing/HFF e para a Noticias do Dia ao mover a publicacao para um
REM  checkout fora do Drive. Por isso o PROMPT abaixo substitui, em TODOS
REM  os caminhos de escrita/publicacao da Seccao 6 e 7 (render de saida,
REM  copia-espelho, "git -C"), o prefixo
REM  "G:\My Drive\Claude_PRJ\personal-system" por
REM  "C:\Users\rafai\Documents\github\personal-system" -- nunca o valor
REM  literal do documento. As restantes leituras (preflight, credenciais
REM  OAuth em G:\My Drive\Claude_PRJ\, planilha Espelho_Notificacoes) nao
REM  mudam -- vivem fora do repo git, sem risco de corrupcao.
REM
REM  Dependencia Python (Seccao 4 da rotina): antes da primeira corrida
REM  agendada, correr uma vez a mao:
REM     python -m pip install -r "G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\Notificacoes\requirements.txt"
REM  Nao repetido a cada corrida deste .bat (custaria tempo sem
REM  necessidade) -- se faltar alguma dependencia, o preflight reporta o
REM  erro claramente e a corrida para, tal como qualquer outra falha.
REM
REM  Credenciais Google Sheets: OAuth local via
REM  G:\My Drive\Claude_PRJ\credentials.json + token.json (Seccao 4). Se o
REM  token estiver expirado/revogado, o PROMPT abaixo instrui a parar e
REM  reportar -- uma corrida agendada sem ninguem a ver nao pode renovar
REM  um OAuth token interactivamente.
REM
REM  A resposta completa do Claude (--output-format json) fica sempre
REM  gravada em _notificacoes_llm_log.json, por isso ha sempre rasto mesmo
REM  quando corre sem ninguem a ver.
REM
REM  Modelo fixo (--model claude-sonnet-5): sem isto, a corrida usaria o
REM  que estiver definido por omissao nesta instalacao do Claude Code --
REM  podia mudar sem aviso se o modelo por omissao for trocado noutro
REM  contexto. Sonnet 5 por escolha explicita do Rafa: a rotina e
REM  sobretudo classificacao/triagem por origem a partir de um manifesto
REM  ja preparado pelo preflight Python -- mais perto do perfil do
REM  Briefing (Sonnet 5) do que da Noticias do Dia (Opus 5, mais sintese
REM  multi-fonte).
REM
REM  Primeira corrida: testa isto a mao de dia, a ver o log, antes de
REM  confiares nele sem vigilancia -- nunca foi corrido num Windows real
REM  a partir do Agendador de Tarefas.
REM
REM  Sincronizacao automatica com origin/main: sessoes de Claude Code na
REM  cloud podem publicar directamente em main a qualquer momento -- se
REM  este checkout local ficar para tras, o proprio commit desta rotina
REM  pode falhar no git push por divergencia (mesmo problema confirmado no
REM  Briefing em 2026-09-18). Por isso sincronizamos sempre primeiro, com
REM  --ff-only (nunca cria merge commit sozinho; se nao conseguir avancar
REM  de forma linear, para e reporta em vez de arriscar).
REM ======================================================================

chcp 65001 >nul
setlocal

set "REPO=C:\Users\rafai\Documents\github\personal-system"
set "OUT=G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\Notificacoes\_notificacoes_llm_log.json"
set "PROMPT=Passo nao-interactivo da rotina de Notificacoes, disparado pelo Agendador de Tarefas sem ninguem a ver -- nunca pares a pedir confirmacao, publicar e sempre o fim normal desta corrida (regra do Rafa). Executa agora a rotina de Notificacoes (instrucoes_notificacoes.md, pasta de instrucoes do Drive, usar sempre a copia de createdTime mais recente), em ativacao DIRECTA, ambiente LOCAL (este e o PC do Rafa, com o Drive sincronizado em G:) -- segue sempre a Seccao 0 'ambiente local/Codex': Python faz o trabalho mecanico, tu so interpretas e rediges o JSON canonico. 1) Confirma a data real em Lisboa (Passo Zero, Seccao 3) antes de tudo. 2) Corre o preflight: python \"G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\Notificacoes\preflight_notificacoes.py\" --date AAAA-MM-DD (com a data confirmada no passo 1). Se a autenticacao Google Sheets falhar (token OAuth expirado/revogado) ou qualquer outro erro impedir o preflight de completar, para AQUI e relata o erro exacto -- nao tentes contornar nem inventar dados. 3) Le o manifesto (notificacoes_preflight_AAAA-MM-DD.json) e o draft canonico (notificacoes_canonical_draft_AAAA-MM-DD.json) que o preflight gerou. Segue a Seccao 5 -- produz APENAS o JSON canonico final (notificacoes_canonical_final_AAAA-MM-DD.json): highlights realmente relevantes, resumo por origem, prioridade (alta/media/baixa/ruido), accao sugerida (revisar/lido/manter), mensagens exemplares ja redigidas de forma segura. Nunca fazer scraping manual, nunca reescrever HTML a mao, nunca usar API OpenAI, nunca expor codigos de autenticacao/segredos/mensagens pessoais sensiveis verbatim -- resumir em vez de citar. 4) Renderiza (Seccao 6): python \"Templates\notificacoes\render_notificacoes.py\" notificacoes_canonical_final_AAAA-MM-DD.json \"C:\Users\rafai\Documents\github\personal-system\agendas\notificacoes\index.html\" -- ATENCAO: usa sempre este caminho de saida C:\Users\rafai\Documents\github\personal-system\..., NUNCA o G:\My Drive\Claude_PRJ\personal-system\... que o documento da rotina mostra como exemplo -- esse checkout tem o git corrompido pela sincronizacao do proprio Drive (erro conhecido: fatal: git show-ref: bad ref refs/tags/desktop.ini), exactamente como ja foi corrigido para o Briefing/HFF e a Noticias do Dia. 5) Copia o mesmo HTML renderizado para C:\Users\rafai\Documents\github\personal-system\agendas\agendas\notificacoes\index.html (o espelho da Seccao 6, mesmo motivo -- destination_dir=agendas do Cloudflare Pages exige as duas copias). 6) Publica (Seccao 7), sempre a partir do checkout C:\Users\rafai\Documents\github\personal-system, nunca do G:\...: git -C \"C:\Users\rafai\Documents\github\personal-system\" add agendas/notificacoes/index.html agendas/agendas/notificacoes/index.html, depois git -C \"C:\Users\rafai\Documents\github\personal-system\" commit -m \"[notificacoes] atualiza triagem\", depois git -C \"C:\Users\rafai\Documents\github\personal-system\" push origin main. Nao incluir ficheiros nao relacionados (nunca desktop.ini nem alteracoes locais em CLAUDE.md). Se o push falhar, para e relata o erro exacto -- nunca fingir sucesso nem publicar por outra via. 7) No fim escreve um resumo curto: data-alvo, quantas origens/mensagens foram processadas, se a pagina publicou com sucesso nos dois caminhos, e a estimativa aproximada de tokens da Seccao 8 (Leitura/entrada, Raciocinio/sintese, JSON final/redaccao, Total)."

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

claude -p "%PROMPT%" --model claude-sonnet-5 --permission-mode bypassPermissions --output-format json > "%OUT%" 2>&1
set "RC=%ERRORLEVEL%"

type "%OUT%"
echo.
if "%RC%"=="0" (
    echo [OK] Notificacoes concluida sem erros.
) else (
    echo [ATENCAO] Notificacoes terminou com erros. Codigo de saida: %RC%
    echo Ver detalhe em: %OUT%
)

exit /b %RC%

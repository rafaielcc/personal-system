# Rotinas Python da Agenda (cópia versionada)

Cópia **versionada** das rotinas Python do projecto Agenda. A cópia de execução vive
no Google Drive, em `G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\`, porque é de lá
que a máquina do Rafa (e o Agendador de Tarefas do Windows) as corre.

Existe aqui pelo mesmo motivo que `scripts/gmail_articles_briefing/`: o Drive **não
edita ficheiros in-place** — cada correcção cria um ficheiro novo, sem histórico e com
risco de ficarem duas cópias com o mesmo nome. No git há diff, histórico e uma única
fonte de verdade para o código.

**Regra:** editar aqui primeiro, correr o `--self-test` da rotina alterada, e só depois
copiar para o Drive (substituindo a cópia lá, e apagando o ficheiro antigo se o Drive
tiver criado um duplicado).

| Ficheiro | O que faz |
|---|---|
| `X_briefing_pre.py` | Recolha mecânica do Briefing (Calendar, Gmail, Todoist, Espelho HFF, meteorologia) → um JSON em `X_Outputs`. Não julga nada, não escreve texto, não publica. |
| `go_X_briefing_pre.bat` | Atalho Windows que corre o `pre` e grava a consola em `X_Outputs\_briefing_pre_log.txt`. Sem `pause`, para não pendurar a tarefa agendada. |
| `X_dashboard_pre.py` | Recolha mecânica do Dashboard (Módulo 5): contagens/tempo (reaproveita o `_briefing.json` mais recente, não repete leitura de Calendar/Todoist) + pré-filtro `needs_action` de Artigos/CIRPED/TestMe (git log para Artigos, chama `preflight_cirped.py` para CIRPED, heurística nova via `Espelho_testme` para TestMe — ver `INSTRUCOES_DASHBOARD.md` Secção 4) → um JSON em `X_Outputs`. |
| `go_dashboard_llm.bat` | Substitui `go_briefing_llm.bat` no 2º slot do Agendador de Tarefas (06:30, seg-sex): corre `X_dashboard_pre.py`, depois `claude -p` não-interactivo que interpreta o Briefing (mesmo trabalho que o antigo `go_briefing_llm.bat`), publica Briefing/HFF/BO, monta e publica o JSON canónico do Dashboard, e acciona TestMe/CIRPED/Artigos só se o pré-filtro disser que há algo por fazer. **Ainda não testado num Windows real** — primeira corrida deve ser a mão, de dia, com o log a ser observado. |
| `X_lazer_pre.py` | Recolha mecânica da Agenda de Lazer. Incorpora os quatro exportadores do antigo `Go_All_events.bat`, lê Calendar/Sheet/perfil/feedback/lista sazonal/meteorologia/web e entrega um único JSON completo à LLM. |
| `go_X_lazer_pre.bat` | Atalho diário e não-interactivo do pré de Lazer; grava o log em `X_Outputs\lazer\_lazer_pre_log.txt`. |
| `go_lazer_llm.bat` | Reutiliza um pré válido, pede à LLM apenas a curadoria do JSON final e executa validação, renderização e publicação automática. Não deve ser agendado até a periodicidade ser definida. |
| `agenda_lazer\` | Cópia versionada do postflight, render, template, extractor MotelX e utilitários da rotina de Lazer. |

Na execução, estes ficheiros vivem em `G:\My Drive\Claude_PRJ\Agenda`:

- `X_lazer_pre.py`, `go_X_lazer_pre.bat` e `go_lazer_llm.bat` em `X_Rotinas_Python\`;
- postflight e extractores em `X_Rotinas_Python\Agenda_Lazer\`;
- render/template/utilitários em `Templates\agenda_lazer\`.

O pré está agendado no Windows todos os dias às 03:30, na tarefa
`\Agenda_Claude\Agenda - Lazer PRE`. A tarefa usa a sessão interactiva do Rafa, pelo que
corre com a sessão iniciada (inclusive bloqueada), mas não depois de terminar sessão. A LLM
é deliberadamente separada: a sua periodicidade é configurada depois, sem alterar o pré diário. Cada execução bem-sucedida
de `go_lazer_llm.bat` publica automaticamente a página, conforme autorização permanente
do Rafa; a publicação continua condicionada à validação limpa do JSON e do HTML.

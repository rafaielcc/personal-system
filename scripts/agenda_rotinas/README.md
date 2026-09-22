# Rotinas Python da Agenda (cópia versionada)

Cópia **versionada** das rotinas Python do projecto Agenda. A cópia de execução vive
no Google Drive, em `G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\`, porque é de lá
que a máquina do Rafa (e o Agendador de Tarefas do Windows) as corre.

Existe aqui pelo mesmo motivo que `scripts/gmail_articles_briefing/`: o Drive **não
edita ficheiros in-place** — cada correcção cria um ficheiro novo, sem histórico e com
risco de ficarem duas cópias com o mesmo nome. No git há diff, histórico e uma única
fonte de verdade para o código.

**Regra:** editar aqui primeiro, correr `python3 X_briefing_pre.py --self-test`, e só
depois copiar para o Drive (substituindo a cópia lá, e apagando o ficheiro antigo se o
Drive tiver criado um duplicado).

| Ficheiro | O que faz |
|---|---|
| `X_briefing_pre.py` | Recolha mecânica do Briefing (Calendar, Gmail, Todoist, Espelho HFF, meteorologia) → um JSON em `X_Outputs`. Não julga nada, não escreve texto, não publica. |
| `go_X_briefing_pre.bat` | Atalho Windows que corre o `pre` e grava a consola em `X_Outputs\_briefing_pre_log.txt`. Sem `pause`, para não pendurar a tarefa agendada. |
| `X_dashboard_pre.py` | Recolha mecânica do Dashboard (Módulo 5): contagens/tempo (reaproveita o `_briefing.json` mais recente, não repete leitura de Calendar/Todoist) + pré-filtro `needs_action` de Artigos/CIRPED/TestMe (git log para Artigos, chama `preflight_cirped.py` para CIRPED, heurística nova via `Espelho_testme` para TestMe — ver `INSTRUCOES_DASHBOARD.md` Secção 4) → um JSON em `X_Outputs`. |
| `go_dashboard_llm.bat` | Substitui `go_briefing_llm.bat` no 2º slot do Agendador de Tarefas (06:30, seg-sex): corre `X_dashboard_pre.py`, depois `claude -p` não-interactivo que interpreta o Briefing (mesmo trabalho que o antigo `go_briefing_llm.bat`), publica Briefing/HFF/BO, monta e publica o JSON canónico do Dashboard, e acciona TestMe/CIRPED/Artigos só se o pré-filtro disser que há algo por fazer. **Ainda não testado num Windows real** — primeira corrida deve ser a mão, de dia, com o log a ser observado. |

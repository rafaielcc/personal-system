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

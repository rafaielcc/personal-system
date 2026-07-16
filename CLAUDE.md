# Projeto AII — contexto para o Claude Code

Este repositório (`rafaielcc/personal-system`) é o backend de código do projeto pessoal de investimentos do Rafa ("AII"). As **instruções das rotinas não vivem aqui** — vivem no Google Drive, e são lidas em tempo de execução (nunca copiadas para o repo, para não haver duas fontes de verdade desincronizadas). Este ficheiro só dá o contexto que uma sessão de Code precisa para executar essas rotinas corretamente, sem o Rafa ter de reexplicar o projeto a cada nova conversa.

## Convenção de nomes

- `AII_Z_<Nome>.md` = ficheiro de ROTINA (protocolo de execução, instruções). Lido sempre na íntegra antes de agir.
- `AII_0_<Nome>_<data>.md` = RELATÓRIO gerado por uma rotina.
- Cada rotina pode ter várias cópias antigas na mesma pasta do Drive com o mesmo título (o Drive não suporta edição in-place; cada correção gera um ficheiro novo). **Usar sempre o de `createdTime` mais recente** — nunca assumir que o primeiro resultado da busca é o correto.

## Pastas do Drive (IDs fixos)

- **Pasta de instruções** (todos os `AII_Z_*.md`, incluindo o histórico de versões): `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`
- **Pasta de relatórios** (`Relatorios/AII`, onde os `AII_0_*.md` são lidos e gravados): `19IlmZ5GwFj6iF2OBbMmIvyuDA33s8u04`
- **Histórico de versões de todas as rotinas**: `AII_Z_CHANGELOG.md`, na pasta de instruções. Só consultar se precisares de entender a evolução de uma regra — não é preciso lê-lo para executar uma rotina.
- **Perfil do investidor / contexto geral do projeto**: `AII_Z_SYSTEM_PROMPT_REVISTO.md`, na pasta de instruções — **é o único destes documentos actualizado**. Existem dois ficheiros irmãos mais antigos na mesma pasta, `AII_Z_Orientacoes_Gerais.md` e `AII_Z_SYSTEM_PROMPT.MD.md` (na prática cópias idênticas um do outro) — ambos desactualizados, com pelo menos duas falhas confirmadas: descrevem o formato errado dos marcadores da planilha "Espelho carteira" (formato que nunca existiu, já corrigido no Revisto) e não mencionam de todo a rotina Decisões e Reflexões nem a pasta de staging `RELEASES_EXTRACAO` usada pela Análise de Empresa. **Nunca usar estes dois ficheiros antigos como fonte** — pendente de o Rafa os apagar do Drive; se ainda aqui estiverem, ignorar.

## Regra importante: perfil do investidor nesta sessão

As rotinas foram escritas para um projeto do claude.ai onde o perfil do investidor já vem embutido no system prompt do projeto ("Ativação direta"). **Uma sessão de Claude Code não tem esse contexto** — por isso, ao executar QUALQUER rotina AII a partir daqui, ler sempre `AII_Z_SYSTEM_PROMPT_REVISTO.md` primeiro para obter o perfil e o contexto geral, mesmo quando a própria rotina disser que isso "não é preciso" na ativação direta. Para tudo o resto (apresentar resultados no chat, gerar ficheiros, publicar HTML/GitHub), seguir a ativação direta normalmente — o Rafa está a pedir diretamente, só falta o perfil em contexto.

## Rotinas disponíveis (skills)

Cada rotina tem um skill próprio em `.claude/skills/`, que só aponta para o ficheiro certo no Drive (nunca contém uma cópia da rotina):

| Comando | Rotina |
|---|---|
| `/noticias-do-dia` | Briefing diário de notícias (`AII_Z_Noticias_do_dia.md`) |
| `/consolidar-projecoes` | Avaliação fundamentalista consolidada (`AII_Z_Consolidar_Projecoes.md`) |
| `/analise-carteira` | Análise e decisão sobre a carteira atual (`AII_Z_Analise_Carteira.md`) |
| `/analise-empresa` | Análise fundamentalista de uma empresa específica (`AII_Z_Instrucoes_Analise_Empresa.md`) |
| `/organizar-setor` | Reorganização de um ficheiro setorial (`AII_Z_Organizar_Setor.md`) |
| `/decisoes-e-reflexoes` | Registo de discussões/decisões ad-hoc de investimento (`AII_Z_Decisoes_e_Reflexoes.md`) |

## Ferramentas necessárias

Google Drive (`search_files`, `download_file_content`, `create_file`) e GitHub (para publicação de HTML, quando a rotina o pedir) têm de estar disponíveis na sessão. Se uma busca no Drive devolver vazio inesperadamente, tentar de novo com `parentId` explícito antes de concluir que o ficheiro não existe — já houve falsos-negativos.

## Planilha "Espelho Radar" (fonte viva de cotações e carteira)

ID `1g7JBnpEkaYZQl2SBGYmooZhOBYqOa0ER2o3F1yPkSnA`, aba única "Main". A secção Carteira e a secção Vigiar estão na mesma folha, separadas pela linha-marcador `------vigiar - - - - -`. É a fonte única de cotações ao vivo e de posições da carteira — nunca usar cotações datadas dos ficheiros `AII_0_` para cálculos.

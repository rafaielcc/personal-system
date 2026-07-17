---
name: sugestao-destinos
description: Executa o módulo "Sugestão de Destinos" do projeto Viagens (Travel OS) — consultor de viagem que sugere destinos personalizados a partir do perfil do Rafa, do histórico de feedback e de um questionário. Use quando o Rafa pedir "sugestão de destinos", "ideia de viagem", "não sei para onde ir", "inspira-me", "surpreende-me", "onde me recomendas ir?" ou variantes, no contexto do projeto de viagens.
---

# Skill: Sugestão de Destinos (Viagens)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se [`viagens/CLAUDE.md`](../../../viagens/CLAUDE.md) deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas/ficheiros do Drive e o contexto geral do projecto Viagens).
2. Ler `System_prompt_Viagens.md.md` (Drive ID `1ZAThYJFFGNT5BIDa4lUohR1ZeabJyhhO`) — obrigatório mesmo que a rotina diga que não é preciso numa "activação directa"; uma sessão de Code não tem o system prompt do projecto pré-carregado.
3. Procurar no Drive, pasta Viagens (ID `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`), o ficheiro `INSTRUCOES_SUGESTAO_DESTINOS.md` (se houver mais do que uma cópia com o mesmo título, usar sempre a de `createdTime` mais recente). Descarregar e ler na íntegra.
4. Seguir a rotina tal como descrita, incluindo a leitura obrigatória de `rafa_profile.md` (ID `1EKv0dfaB_N-WZC1yMJpJkP6GckjCgDXb`) e `feedback_log.md` (ID `1Dkc3C4fsaJc0tRfnQkTCIQdFCLga3He4`) antes de correr o questionário (`questionario_destinos.json`/`.jsx`) e antes de sugerir qualquer destino — as sugestões nascem da combinação do perfil + histórico + questionário, nunca só do questionário.
5. Pesquisa web obrigatória para cada destino candidato (clima nas datas, eventos, lotação, acessibilidade, custo de vida) antes de gerar o relatório.
6. Quando o Rafa escolher um destino, passar o controlo ao skill `planear-viagem` — reutilizar as respostas já dadas (datas, companhia, orçamento, transporte), não voltar a perguntar.

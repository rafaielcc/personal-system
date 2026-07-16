---
name: analise-empresa
description: Executa a rotina "Análise de Empresa" do projeto AII (análise fundamentalista de um ticker específico, a partir de release/ITR/transcrição). Use quando o Rafa pedir para analisar uma empresa/ticker específico, "análise de empresa", ou fornecer um release/ITR para análise, no contexto do projeto AII/carteira de investimentos.
---

# Skill: Análise de Empresa (AII)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se `CLAUDE.md` deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas do Drive e a convenção do projeto AII).
2. Procurar no Google Drive, na pasta de instruções (ID `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`), o ficheiro com título `AII_Z_Instrucoes_Analise_Empresa.md` (nota: o nome do ficheiro NÃO é "AII_Z_Analise_Empresa.md" — confirmar o título exato antes de assumir que não existe). Pode haver mais do que um resultado (cópias antigas) — usar sempre o de `createdTime` mais recente.
3. Descarregar e ler o ficheiro por completo. Seguir as instruções na íntegra, incluindo a secção IDENTIFICAÇÃO OBRIGATÓRIA (confirmar ticker/empresa/setor com o Rafa antes de avançar) e o pré-processamento de documentos brutos via script (`extract_resultado.py`), quando aplicável.
4. Ler também `AII_Z_SYSTEM_PROMPT_REVISTO.md` (mesma pasta) para o perfil do investidor e o contexto geral do projeto — ver nota em `CLAUDE.md` sobre isto ser sempre necessário no Code.
5. A secção 11 ("faria sentido para mim?") é exploratória — nunca é decisão de carteira; essa cabe exclusivamente à rotina Análise de Carteira.

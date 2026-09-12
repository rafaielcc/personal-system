---
name: cv
description: Sistema de Registo Curricular do Rafa (percurso profissional médico — grau de consultor PT, Portfolio Pathway GMC/UK, relatório ULSASI, CV). Dois modos. Use quando o Rafa escrever "/cv" seguido de conteúdo para despejar (texto, ficheiro, link sobre uma cirurgia, curso, publicação, aula, certificado, actividade); ou "/cv" sozinho para arquivar o que está pendente no INBOX. Não usar para o projeto AII (investimentos) nem para as agendas.
---

# Skill: Registo Curricular (cv)

Este skill é um PONTEIRO. As regras do sistema `cv` vivem no Drive, no `CLAUDE.md` da
pasta `cv` — nunca aqui. Executar uma cópia guardada neste repositório seria executar
regras desactualizadas.

**Este repositório é público.** Por isso este ficheiro não contém IDs de pastas do Drive
nem qualquer dado do sistema `cv`, que é privado. A localização descobre-se por busca.

## Localizar a pasta

1. Buscar no Drive `title = 'INBOX.md'`. É o marcador da raiz do `cv` — o `parentId` do
   resultado **é** a pasta `cv`.
2. Se vier vazio, tentar de novo antes de concluir que não existe (já houve
   falsos-negativos no conector). Só depois perguntar ao Rafa.
3. A partir daí, listar por `parentId` para encontrar `CLAUDE.md`, `entradas/`,
   `logbook/`, `dossies/`, `rotinas/`, `provas/`, `reflexoes/`, `saidas/`, `_versoes/`.

## Sempre, antes de agir

Ler o `CLAUDE.md` da pasta `cv` na íntegra. Define os quatro destinos do registo, os
campos obrigatórios das entradas, os códigos de papel operatório da GMC e a regra de
supervisão. Nada neste ficheiro substitui o que lá está.

## Modo A — `/cv <conteúdo>` (despejar)

O Rafa passou texto, um ficheiro ou um link.

1. Anexar **em bruto** à secção `## Por processar` do `INBOX.md`. Sem interpretar, sem
   estruturar, sem fazer perguntas. Prefixar com a data.
2. Gravar a versão nova do `INBOX.md` e mover a anterior para `_versoes/` com o título
   datado (o Drive não edita in-place — ver "Versionamento" abaixo).
3. Responder numa linha só: o que ficou guardado. Não processar nada agora.

O objectivo deste modo é ser rápido. Ele pode estar entre duas cirurgias.

## Modo B — `/cv` sozinho (arquivar)

Não veio conteúdo, portanto há que processar o pendente.

1. Ler o `INBOX.md`.
2. Para cada item em `## Por processar` que **não** esteja marcado `[rascunho]`, criar
   uma entrada em `entradas/` a partir de `entradas/_TEMPLATE.md`, nomeada
   `AAAA-MM-slug.md`, com o bloco de metadados preenchido.
3. Mover o item para `## Processado`, com a data e o ID da entrada criada.
4. Dizer em duas linhas o que foi arquivado. **Arquivar primeiro, mostrar depois** — não
   pedir confirmação prévia; ele corrige se for preciso.
5. Se o INBOX estiver vazio, dizê-lo numa linha e parar.

**Nunca escrever reflexões por ele.** Organizar, corrigir português e estruturar o que ele
escreveu, sim. Inventar o que sentiu ou aprendeu, não. Se faltar reflexão, marcar
`reflexao: pendente` e seguir.

## Logbook — acrescentar, nunca refazer

O `logbook/logbook.csv` é incremental. Ler o que já lá está e acrescentar só o que falta;
não regenerar o histórico. A chave de um caso é `PatientCode` + `Date`.

O ficheiro é **anónimo**: leva `PatientCode`, nunca o número de processo. O mapeamento
`PatientCode ↔ processo` vive numa pasta irmã, fora da pasta `cv`, e nunca entra em
repositório nenhum. Ao acrescentar um doente novo, continuar a numeração `CPnnnn`
existente e registar o par no mapeamento.

Regra da GMC que se perde com facilidade: **uma operação = um doente**. Vários
procedimentos no mesmo doente e na mesma sessão são **um** caso, não vários.

## Versionamento no Drive

O conector do Drive não edita ficheiros in-place. Para actualizar qualquer ficheiro:

1. Criar o ficheiro novo com o título definitivo na pasta certa.
2. Mover o antigo para `_versoes/`, renomeando para `<nome>_AAAA-MM-DD_vN.<ext>`.

Nunca deixar duas versões com o mesmo título na mesma pasta — foi o problema que o
projecto AII já teve.

## Gerar saídas

Ainda não implementado. Quando o Rafa pedir um CV, um relatório ou o mapeamento para as
alíneas da grelha portuguesa, dizer que essa parte está por fazer e perguntar se quer
avançar com ela agora.

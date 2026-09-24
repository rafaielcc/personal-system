// Apps Script bound a espelho_lazer. Recebe POST da Agenda de Lazer (icones
// remover/elevar/guardar-futuro/consumido/limpo) e grava uma linha nova —
// append-only, nunca reescreve linhas antigas. A ultima linha por dedup_key
// e a que vale; a proxima geracao da rotina le tudo no preflight local e usa
// so a mais recente por chave.
//
// v3 — 28 Ago 2026: aceita tambem a acao "limpo", usada quando Rafa clica
// de novo num botao de curadoria ja ativo para desfazer a marcacao. O score
// de "consumido" nao e pedido no browser; fica para merge_feedback.py local.
//
// v2 — 22 Ago 2026: coluna nova "nota" (mantida por compatibilidade, mas
// vazia no fluxo atual). setHeaderIfMissing() auto-repara o cabecalho da
// coluna H numa sheet que ja existia com 7 colunas.
//
// DEPLOY (sempre que este ficheiro mudar, ver AGENDA_LAZER_INSTRUCOES LOCAL
// Seccao 0.5):
// 1. Abrir a sheet espelho_lazer -> Extensoes -> Apps Script.
// 2. Colar este ficheiro (substitui o Code.gs vazio).
// 3. Implementar -> Nova implantacao -> tipo "Aplicacao Web".
//    Executar como: Eu (o proprio). Quem tem acesso: Qualquer pessoa.
// 4. Copiar o URL da implantacao (acaba em /exec) e colar na constante
//    APPS_SCRIPT_URL no <script> do template.html da Agenda de Lazer
//    (Drive, Templates/agenda_lazer/template_v9.html). Se o URL ja estiver
//    la de uma implantacao anterior, nao e preciso mexer (ver passo 5).
// 5. Sempre que este ficheiro mudar: Implementar -> Gerir implantacoes ->
//    editar (icone de lapis) -> Versao "Nova versao" -> Implementar.
//    O URL do passo 4 mantem-se o mesmo, nao e preciso trocar no template.

var SHEET_NAME = "espelho_lazer"; // nome da folha dentro da spreadsheet
var TTL_ELEVAR_DIAS = 14; // validade de um "elevar" quando o item nao tem data propria

function doPost(e) {
  var resposta = { ok: false };
  try {
    var payload = JSON.parse(e.postData.contents);
    var acao = payload.acao;
    var acoesValidas = ["removido", "elevar", "guardado_futuro", "consumido", "limpo"];
    if (acoesValidas.indexOf(acao) === -1) {
      throw new Error("acao desconhecida: " + acao);
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
    setHeaderIfMissing(sheet);

    var agora = new Date();
    var expiraEm = "";
    if (acao === "elevar") {
      if (payload.date) {
        expiraEm = payload.date; // expira na propria data do evento
      } else {
        var d = new Date(agora.getTime());
        d.setDate(d.getDate() + TTL_ELEVAR_DIAS);
        expiraEm = Utilities.formatDate(d, "GMT", "yyyy-MM-dd");
      }
    }

    sheet.appendRow([
      agora.toISOString(),
      payload.dedup_key || "",
      payload.title || "",
      payload.category || "",
      acao,
      payload.date || "",
      expiraEm,
      payload.nota || "",
    ]);

    resposta.ok = true;
  } catch (err) {
    resposta.error = String(err);
  }
  return ContentService.createTextOutput(JSON.stringify(resposta))
    .setMimeType(ContentService.MimeType.JSON);
}

// Auto-repara o cabecalho da coluna H ("nota") numa sheet que ja existia
// antes desta versao (so tinha 7 colunas) — corre em todo doPost, mas so
// escreve se a celula ainda nao disser "nota" (idempotente, custo minimo).
function setHeaderIfMissing(sheet) {
  var cabecalhoH = sheet.getRange(1, 8);
  if (cabecalhoH.getValue() !== "nota") {
    cabecalhoH.setValue("nota");
  }
}

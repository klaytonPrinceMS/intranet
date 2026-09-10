/**
 * impressao.js — Utilitários de impressão para o módulo Solicitação de Impressão.
 *
 * O navegador NÃO expõe via JS padrão a lista de impressoras instaladas
 * (Web Print API é experimental/limitada). Estratégia:
 *  1. Tenta navigator.getPrinters() (Chrome experimental, atrás de flag) para
 *     listar nomes de impressoras, se disponível.
 *  2. Caso contrário, usa window.print() em uma nova aba com o PDF já preparado,
 *     deixando o diálogo nativo do SO escolher a impressora.
 *
 * Funções expostas no window:
 *  - listarImpressoras(): Promise<string[]> (nomes; pode vir vazio)
 *  - imprimirPdf(url, nomeImpressora): abre o PDF e dispara window.print()
 *  - printSolicitacao(id): dispara impressão para a solicitação (precisa do blob)
 */

(function () {
  "use strict";

  // Lista (cache) de impressoras detectadas
  window._impressorasDetectadas = [];

  /**
   * Tenta obter nomes de impressoras via API experimental do Chrome.
   * Retorna Promise que resolve com array (pode ser vazio se indisponível).
   */
  window.listarImpressoras = function () {
    return new Promise(function (resolve) {
      try {
        if (navigator.getPrinters && typeof navigator.getPrinters === "function") {
          navigator
            .getPrinters()
            .then(function (printers) {
              window._impressorasDetectadas = printers || [];
              resolve(window._impressorasDetectadas);
            })
            .catch(function () {
              resolve([]);
            });
        } else if (
          navigator.printers &&
          typeof navigator.printers === "object" &&
          Array.isArray(navigator.printers)
        ) {
          window._impressorasDetectadas = navigator.printers;
          resolve(navigator.printers);
        } else {
          resolve([]);
        }
      } catch (e) {
        resolve([]);
      }
    });
  };

  /**
   * Abre o PDF numa nova aba e dispara o diálogo de impressão do SO.
   * nomeImpressora é ignorado pelo window.print() padrão (o SO decide),
   * mas é guardado para logs/compatibilidade futura.
   */
  window.imprimirPdf = function (url, nomeImpressora) {
    var win = window.open(url, "_blank");
    if (!win) {
      alert("Permita pop-ups para imprimir diretamente.");
      return false;
    }
    win.focus();
    // Aguarda o PDF carregar antes de imprimir
    var tentativas = 0;
    var timer = setInterval(function () {
      tentativas++;
      try {
        if (win.document.readyState === "complete" || tentativas > 20) {
          clearInterval(timer);
          if (nomeImpressora) {
            try {
              win.document.title = nomeImpressora;
            } catch (e) {}
          }
          win.print();
        }
      } catch (e) {
        clearInterval(timer);
      }
    }, 300);
    return true;
  };

  /**
   * Dispara a impressão de uma solicitação.
   * urlPdf deve ser fornecida pelo backend (rota de download do PDF preparado).
   * Se não houver urlPdf, o backend deve fornecer via callback.
   */
  window.printSolicitacao = function (id, urlPdf) {
    if (!urlPdf) {
      // Tenta obter do backend via endpoint padrão
      urlPdf = "/solicita-impressao/pdf/" + id;
    }
    return window.imprimirPdf(urlPdf, null);
  };
})();

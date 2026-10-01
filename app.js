/* Equilibra · comportamentos comuns a todas as telas (carregado com defer). */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});

  /* ---------- controles de formulário ---------- */
  $$("input[type=range]").forEach(function (r) {
    var out = document.getElementById(r.id + "-v");
    function upd() { r.style.setProperty("--p", (r.value - r.min) / (r.max - r.min) * 100 + "%"); if (out) out.textContent = r.value + "/10"; }
    r.addEventListener("input", upd); upd();
  });
  $$("[data-mostra]").forEach(function (t) {
    var alvo = document.getElementById(t.dataset.mostra);
    function upd() { if (alvo) alvo.hidden = !t.checked; }
    t.addEventListener("change", upd); upd();
  });
  $$("[data-indicador]").forEach(function (box) {
    var faixa = $("input[type=range]", box), oculto = $("input[type=hidden]", box);
    var valor = $("[data-valor]", box), limpar = $("[data-limpar]", box);
    function marcar() { oculto.value = faixa.value; box.classList.add("avaliado"); valor.textContent = faixa.value + "/10"; valor.classList.remove("vazio"); limpar.hidden = false; }
    faixa.addEventListener("input", marcar); faixa.addEventListener("change", marcar);
    limpar.addEventListener("click", function () { oculto.value = ""; box.classList.remove("avaliado"); valor.textContent = "não avaliado"; valor.classList.add("vazio"); limpar.hidden = true; });
  });
  $$(".cronometro[data-desde]").forEach(function (el) {
    var desde = new Date(el.dataset.desde);
    function upd() { var m = Math.max(0, Math.floor((Date.now() - desde.getTime()) / 60000)); el.textContent = m < 60 ? m + " min" : Math.floor(m / 60) + "h" + String(m % 60).padStart(2, "0"); }
    upd(); setInterval(upd, 30000);
  });
  $$("[data-auto-enviar]").forEach(function (el) { el.addEventListener("change", function () { el.form && el.form.requestSubmit(); }); });
  $$("[data-imprimir]").forEach(function (el) { el.addEventListener("click", function () { window.print(); }); });
  $$("[data-recarregar]").forEach(function (el) { el.addEventListener("click", function () { location.reload(); }); });
  $$("[data-abrir]").forEach(function (el) { el.addEventListener("click", function () { var d = document.getElementById(el.dataset.abrir); if (d) d.open = true; }); });

  /* ---------- confirmação no estilo do app (substitui o confirm do navegador) ---------- */
  var dlg = $("#dlg-confirma");
  $$("form[data-confirma]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (f.dataset.confirmado === "1" || !dlg || !dlg.showModal) { if (!dlg && !confirm(f.dataset.confirma)) e.preventDefault(); return; }
      e.preventDefault();
      var quem = e.submitter;
      $("#dlg-texto").textContent = f.dataset.confirma;
      dlg.showModal();
      dlg.onclose = function () {
        if (dlg.returnValue === "sim") { f.dataset.confirmado = "1"; f.requestSubmit(quem || undefined); }
      };
    });
  });

  /* ---------- trava contra envio duplo (evita pagamentos e registros repetidos) ---------- */
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (e.defaultPrevented || (f.method || "").toLowerCase() !== "post" || f.dataset.livre !== undefined) return;
    if (f.dataset.enviando === "1") { e.preventDefault(); return; }
    f.dataset.enviando = "1";
    var b = e.submitter;
    if (b && b.name) { var h = document.createElement("input"); h.type = "hidden"; h.name = b.name; h.value = b.value; f.appendChild(h); }
    setTimeout(function () { $$("button[type=submit], button:not([type])", f).forEach(function (x) { x.disabled = true; x.setAttribute("aria-busy", "true"); }); }, 0);
  });
  window.addEventListener("pageshow", function () {   // ao voltar pelo histórico, libera os botões
    $$("form[data-enviando]").forEach(function (f) { delete f.dataset.enviando; delete f.dataset.confirmado; });
    $$("button[aria-busy]").forEach(function (b) { b.disabled = false; b.removeAttribute("aria-busy"); });
  });

  /* ---------- avisos (toasts) ---------- */
  $$(".toast").forEach(function (t, i) {
    var fechar = function () { t.classList.add("saindo"); setTimeout(function () { t.remove(); }, 250); };
    t.addEventListener("click", fechar);
    setTimeout(fechar, (t.classList.contains("erro") ? 8000 : 4500) + i * 400);
  });

  /* ---------- painel "Mais" ---------- */
  var mais = $("#folha-mais");
  $$("[data-abrir-mais]").forEach(function (b) { b.addEventListener("click", function () { if (mais && mais.showModal) mais.showModal(); }); });
  if (mais) mais.addEventListener("click", function (e) { if (e.target === mais) mais.close(); });
  $$("[data-fechar]").forEach(function (b) { b.addEventListener("click", function () { var d = b.closest("dialog"); if (d) d.close(b.value || ""); }); });

  /* ---------- puxar para atualizar (o iPhone não faz isso em app instalado) ---------- */
  var instalado = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  var ptr = $(".ptr");
  if (instalado && ptr) {
    var y0 = null, dist = 0;
    document.addEventListener("touchstart", function (e) {
      var alvo = e.target;
      if (window.scrollY > 0 || alvo.closest("input, textarea, select, dialog, [data-indicador], .barra")) { y0 = null; return; }
      y0 = e.touches[0].clientY; dist = 0;
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (y0 === null) return;
      dist = Math.max(0, Math.min(120, e.touches[0].clientY - y0));
      ptr.style.setProperty("--d", dist + "px"); ptr.classList.toggle("pronto", dist > 80);
    }, { passive: true });
    document.addEventListener("touchend", function () {
      if (y0 === null) return;
      if (dist > 80) { ptr.classList.add("carregando"); location.reload(); }
      else ptr.style.setProperty("--d", "0px");
      y0 = null;
    });
  }
})();

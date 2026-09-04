/* ============================================================================
   MR AGENTES — comportamiento de la interfaz
   ----------------------------------------------------------------------------
   Regla de la casa: JavaScript sólo donde hay una interacción real. Nada de
   revelados al hacer scroll, nada de texto que se escribe solo. Si se apaga el
   JS, el sitio sigue completo: el menú queda abierto, el índice queda entero.
   ========================================================================== */

(function () {
  "use strict";

  /* ------------------------------------------------------------------------
     Menú en pantallas angostas
     El <nav> se oculta por CSS sólo bajo 48rem; acá le damos el estado.
     --------------------------------------------------------------------- */
  function initMenu() {
    var btn = document.querySelector("[data-menu-btn]");
    var nav = document.querySelector("[data-menu]");
    if (!btn || !nav) return;

    // Sin JS el botón no sirve, así que sólo aparece cuando JS corrió.
    btn.hidden = false;

    function setOpen(open) {
      btn.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("open", open);
      btn.querySelector("[data-menu-label]").textContent = open ? "Cerrar" : "Menú";
    }

    btn.addEventListener("click", function () {
      setOpen(btn.getAttribute("aria-expanded") !== "true");
    });

    // Escape cierra y devuelve el foco al botón: si abriste con teclado,
    // no deberías quedar perdido en el documento.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        btn.focus();
      }
    });

    // Al pasar a escritorio el menú vuelve a estar siempre visible: hay que
    // limpiar el estado o queda un aria-expanded mintiendo.
    var wide = window.matchMedia("(min-width: 48rem)");
    (wide.addEventListener ? wide.addEventListener.bind(wide, "change") : wide.addListener.bind(wide))(
      function (e) { if (e.matches) setOpen(false); }
    );
  }

  /* ------------------------------------------------------------------------
     Filtro del índice de notas
     Filtra las filas ya presentes en el HTML — no pide nada al servidor y no
     depende de un índice JSON aparte. Texto libre sobre título y bajada, más
     temas acumulables (intersección: sumar temas achica el resultado).
     --------------------------------------------------------------------- */
  function initIndexFilter() {
    var root = document.querySelector("[data-filter]");
    if (!root) return;

    var input = root.querySelector("[data-filter-input]");
    var buttons = Array.prototype.slice.call(root.querySelectorAll("[data-topic]"));
    var counter = root.querySelector("[data-filter-count]");
    var list = document.querySelector("[data-index]");
    if (!input || !list) return;

    var rows = Array.prototype.slice.call(list.children).map(function (li) {
      return {
        el: li,
        haystack: fold(li.textContent),
        topics: (li.getAttribute("data-topics") || "").split("|").filter(Boolean)
      };
    });

    var active = [];

    /* Normaliza para comparar: sin tildes, sin puntuación, minúsculas.
       Buscar "regulacion" tiene que encontrar "regulación". */
    function fold(s) {
      return s
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }

    function apply() {
      var q = fold(input.value);
      var terms = q ? q.split(" ") : [];
      var shown = 0;

      rows.forEach(function (row) {
        var okTopics = active.every(function (t) { return row.topics.indexOf(t) !== -1; });
        var okText = terms.every(function (t) { return row.haystack.indexOf(t) !== -1; });
        var visible = okTopics && okText;
        row.el.hidden = !visible;
        if (visible) shown++;
      });

      if (counter) {
        counter.textContent = shown === rows.length
          ? rows.length + (rows.length === 1 ? " nota" : " notas")
          : shown + " de " + rows.length;
      }

      var empty = document.querySelector("[data-filter-empty]");
      if (empty) empty.hidden = shown !== 0;
    }

    input.addEventListener("input", apply);

    // Escape limpia la búsqueda: es lo que espera cualquiera que haya usado
    // un buscador antes.
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.value) { input.value = ""; apply(); }
    });

    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-topic");
        var i = active.indexOf(t);
        if (i === -1) { active.push(t); } else { active.splice(i, 1); }
        b.classList.toggle("topic--on", i === -1);
        b.setAttribute("aria-pressed", String(i === -1));
        apply();
      });
    });

    apply();
  }


  /* Métrica agregada y sin cookies: nombre del evento y ruta pública, nada más.
     Se respeta Do Not Track. El Worker descarta IP, user-agent, query y cuerpo
     de la nota, por lo que no construye perfiles ni permite identificar visitas. */
  function recordShareMetric(eventName) {
    if (navigator.doNotTrack === "1") return;
    var payload = JSON.stringify({ event: eventName, path: window.location.pathname });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/metrics/v1/events", new Blob([payload], { type: "application/json" }));
        return;
      }
      window.fetch("/api/metrics/v1/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
        credentials: "omit"
      }).catch(function () {});
    } catch (ignore) {}
  }

  /* Compartir una nota sin obligar a copiar y pegar. En navegadores con el
     diálogo nativo se usa ese canal; en escritorio se copia la URL y se lo
     confirma de forma accesible. El enlace de WhatsApp sigue funcionando sin
     JavaScript. */
  function initArticleShare() {
    var btn = document.querySelector("[data-share-url]");
    var status = document.querySelector("[data-share-status]");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-share-url") || window.location.href;
      var title = btn.getAttribute("data-share-title") || document.title;
      if (navigator.share) {
        navigator.share({ title: title, text: title, url: url }).then(function () {
          recordShareMetric("share_native");
        }).catch(function () {});
        return;
      }
      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        if (status) status.textContent = "Copie este enlace: " + url;
        return;
      }
      navigator.clipboard.writeText(url).then(function () {
        if (status) status.textContent = "Enlace copiado. Ya puede enviárselo a quien le pueda servir.";
        recordShareMetric("share_copy");
      }).catch(function () {
        if (status) status.textContent = "Copie este enlace: " + url;
      });
    });

    var whatsapp = document.querySelector("[data-share-whatsapp]");
    if (whatsapp) {
      whatsapp.addEventListener("click", function () { recordShareMetric("share_whatsapp"); });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initMenu(); initIndexFilter(); initArticleShare(); });
  } else {
    initMenu();
    initIndexFilter();
    initArticleShare();
  }
})();

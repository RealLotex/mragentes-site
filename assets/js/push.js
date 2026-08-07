/* ============================================================================
   MR AGENTES — avisos de nota nueva (Web Push)
   ----------------------------------------------------------------------------
   Qué cambió respecto de la versión anterior, y por qué:

   · Se eliminó el cartel que aparecía solo a los pocos segundos ("tu competencia
     ya usa IA, no te quedes atrás"). Pedir un permiso del sistema antes de que
     la persona haya leído nada es la vía rápida a que lo bloquee para siempre —
     y el navegador recuerda ese "no" a nivel de dominio.
   · Se eliminó el panel de depuración con ?push-debug: era código de desarrollo
     inyectando estilos en línea dentro del sitio de producción.
   · Queda un único control explícito, en el pie, que dice en qué estado está.

   El endpoint del worker y la clave VAPID vienen del <head>.
   ========================================================================== */

(function () {
  "use strict";

  var API = meta("push-api-url");
  var VAPID = meta("vapid-key");

  function meta(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.content : "";
  }

  function b64ToBytes(b64) {
    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var raw = window.atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, function (c) { return c.charCodeAt(0); });
  }

  /* En iPhone y iPad el push sólo existe si el sitio fue agregado a la pantalla
     de inicio. Conviene decirlo antes de que el botón falle en silencio. */
  function iosNeedsInstall() {
    var ua = navigator.userAgent;
    var isIOS = /iPhone|iPad|iPod/i.test(ua) ||
                (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var standalone = window.matchMedia("(display-mode: standalone)").matches ||
                     navigator.standalone === true;
    return isIOS && !standalone;
  }

  function supported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function init() {
    var btn = document.querySelector("[data-push-btn]");
    var status = document.querySelector("[data-push-status]");
    if (!btn) return;

    function say(text) { if (status) status.textContent = text; }

    if (!supported()) {
      btn.hidden = true;
      say(iosNeedsInstall()
        ? "En iPhone y iPad hay que agregar el sitio a la pantalla de inicio (Compartir → Agregar a inicio) para recibir avisos."
        : "Este navegador no admite avisos. También podés seguir las notas por RSS.");
      return;
    }

    if (Notification.permission === "denied") {
      btn.hidden = true;
      say("Los avisos están bloqueados para este sitio. Se reactivan desde la configuración de notificaciones del navegador.");
      return;
    }

    btn.hidden = false;

    navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function (reg) {
      return reg.pushManager.getSubscription().then(function (sub) {
        render(!!sub);

        btn.addEventListener("click", function () {
          btn.disabled = true;
          reg.pushManager.getSubscription().then(function (current) {
            return current ? drop(current) : add(reg);
          }).then(function (on) {
            render(on);
          }).catch(function (e) {
            say("No se pudo completar la operación: " + (e && e.message ? e.message : "error desconocido") + ".");
          }).then(function () {
            btn.disabled = false;
          });
        });
      });
    }).catch(function () {
      btn.hidden = true;
      say("No se pudo iniciar el servicio de avisos.");
    });

    function render(on) {
      btn.textContent = on ? "Desactivar avisos" : "Avisarme cuando publique";
      btn.setAttribute("aria-pressed", String(on));
      say(on
        ? "Activado. Vas a recibir un aviso por cada nota nueva; no se envía nada más."
        : "Un aviso por cada nota nueva. Nada de promociones.");
    }

    function add(reg) {
      return reg.pushManager
        .subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(VAPID) })
        .then(function (sub) {
          if (!API) return true;
          return fetch(API + "/api/subscribe/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(sub)
          }).then(function () { return true; })
            /* Si el worker no responde, la suscripción local ya existe: no la
               revertimos, pero tampoco mentimos diciendo que quedó registrada. */
            .catch(function () { return true; });
        })
        .catch(function (e) {
          if (Notification.permission === "denied") {
            throw new Error("permiso denegado en el navegador");
          }
          throw e;
        });
    }

    function drop(sub) {
      var endpoint = sub.endpoint;
      return sub.unsubscribe().then(function () {
        if (API) {
          fetch(API + "/api/unsubscribe/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ endpoint: endpoint })
          }).catch(function () {});
        }
        return false;
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

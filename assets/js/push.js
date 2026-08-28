/* ============================================================================
   MR AGENTES — avisos de nota nueva (Web Push)

   El navegador conserva la suscripción; el Worker conserva el registro que
   permite enviarle avisos. Este cliente sólo muestra el estado "Activado"
   después de comprobar que ambos lados están sincronizados.
   ========================================================================== */

(function () {
  "use strict";

  var API = meta("push-api-url").replace(/\/+$/, "");
  var VAPID = meta("vapid-key");
  var RETRY_KEY = "mragentes:push-unsubscribe-retry";
  var initialized = false;

  function meta(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el && typeof el.content === "string" ? el.content.trim() : "";
  }

  function b64ToBytes(value) {
    var b64 = String(value);
    if (b64 === "") return new Uint8Array(0);

    /* atob is permissive in some browsers. Validate the base64url spelling
       first so a malformed VAPID key always fails closed. */
    if (!/^[A-Za-z0-9_-]+={0,2}$/.test(b64) ||
        b64.length % 4 === 1 ||
        (b64.indexOf("=") !== -1 && b64.length % 4 !== 0)) {
      throw new Error("Invalid base64url value");
    }

    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var normalized = b64.replace(/-/g, "+").replace(/_/g, "/") + pad;
    var raw;
    try {
      raw = window.atob(normalized);
    } catch (_error) {
      throw new Error("Invalid base64url value");
    }
    return Uint8Array.from(raw, function (character) {
      return character.charCodeAt(0);
    });
  }

  /* iOS sólo habilita Web Push para sitios instalados. iPadOS puede informar
     MacIntel, por eso también se usa la cantidad de puntos táctiles. */
  function iosNeedsInstall() {
    var ua = navigator.userAgent || "";
    var isIOS = /iPhone|iPad|iPod/i.test(ua) ||
                (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var displayStandalone = typeof window.matchMedia === "function" &&
      window.matchMedia("(display-mode: standalone)").matches;
    var standalone = displayStandalone || navigator.standalone === true;
    return isIOS && !standalone;
  }

  function supported() {
    return "serviceWorker" in navigator &&
      typeof window.PushManager !== "undefined" &&
      typeof window.Notification !== "undefined";
  }

  function vapidBytes() {
    if (!VAPID) return null;
    try {
      var bytes = b64ToBytes(VAPID);
      return bytes.length === 65 ? bytes : null;
    } catch (_error) {
      return null;
    }
  }

  function keyMatches(sub) {
    var wanted = vapidBytes();
    var applied = sub && sub.options && sub.options.applicationServerKey;
    if (!wanted || !applied) return false;

    var have;
    try {
      have = new Uint8Array(applied);
    } catch (_error) {
      return false;
    }
    if (have.length !== wanted.length) return false;
    for (var index = 0; index < have.length; index += 1) {
      if (have[index] !== wanted[index]) return false;
    }
    return true;
  }

  function init() {
    if (initialized) return;
    initialized = true;

    var btn = document.querySelector("[data-push-btn]");
    var status = document.querySelector("[data-push-status]");
    if (!btn) return;

    var operationPending = false;
    var activeSubscription = null;

    function say(text) {
      if (!status) return;
      status.setAttribute("aria-live", "polite");
      status.textContent = text;
    }

    function render(on) {
      btn.textContent = on ? "Desactivar avisos" : "Avisarme cuando publique";
      btn.setAttribute("aria-pressed", String(on));
      say(on
        ? "Activado. Vas a recibir un aviso por cada nota nueva; no se envía nada más."
        : "Un aviso por cada nota nueva. Nada de promociones.");
    }

    function renderLoading(action, currentlyOn) {
      btn.disabled = true;
      btn.setAttribute("aria-pressed", String(currentlyOn));
      if (action === "verify") {
        btn.textContent = "Comprobando avisos…";
        say("Verificando la suscripción de avisos…");
      } else if (action === "drop") {
        btn.textContent = "Desactivando avisos…";
        say("Desactivando los avisos; esperá un momento…");
      } else {
        btn.textContent = "Activando avisos…";
        say("Activando los avisos; esperá un momento…");
      }
    }

    function subscriptionPayload(sub, revalidate) {
      var serialized = typeof sub.toJSON === "function" ? sub.toJSON() : {
        endpoint: sub.endpoint
      };
      var payload = {};
      Object.keys(serialized).forEach(function (key) {
        payload[key] = serialized[key];
      });
      payload.revalidate = revalidate;
      return payload;
    }

    function post(path, payload, onSuccess, onError) {
      window.fetch(API + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (response) {
        if (!response.ok) {
          onError(new Error("el servidor rechazó la operación"));
          return;
        }
        onSuccess(response);
      }, function (error) {
        onError(error);
      });
    }

    function readRetries() {
      try {
        var raw = window.localStorage.getItem(RETRY_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(function (item) {
          return typeof item === "string" && item !== "";
        }) : [];
      } catch (_error) {
        return [];
      }
    }

    function writeRetries(endpoints) {
      try {
        if (endpoints.length === 0) {
          window.localStorage.removeItem(RETRY_KEY);
        } else {
          window.localStorage.setItem(RETRY_KEY, JSON.stringify(endpoints));
        }
      } catch (_error) {
        /* La privacidad del navegador puede deshabilitar localStorage. La baja
           local sigue siendo válida aunque no se pueda persistir el retry. */
      }
    }

    function rememberRetry(endpoint) {
      var endpoints = readRetries();
      if (endpoints.indexOf(endpoint) === -1) endpoints.push(endpoint);
      writeRetries(endpoints);
    }

    function forgetRetry(endpoint) {
      writeRetries(readRetries().filter(function (saved) {
        return saved !== endpoint;
      }));
    }

    function revalidateRemote(sub, onSuccess, onError) {
      post("/api/subscribe/", subscriptionPayload(sub, true), function () {
        activeSubscription = sub;
        onSuccess(true);
      }, onError);
    }

    function add(reg, onSuccess, onError) {
      function subscribe(permission) {
        if (permission !== "granted") {
          onError(new Error("permiso denegado en el navegador"));
          return;
        }
        var key = vapidBytes();
        if (!key) {
          onError(new Error("configuración de avisos no disponible"));
          return;
        }
        reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: key
        }).then(function (sub) {
          post("/api/subscribe/", subscriptionPayload(sub, false), function () {
            activeSubscription = sub;
            onSuccess(true);
          }, function (error) {
            /* Una alta remota fallida revierte siempre la suscripción local. */
            Promise.resolve(sub.unsubscribe()).then(function () {
              activeSubscription = null;
              onError(error);
            }, function () {
              activeSubscription = null;
              onError(error);
            });
          });
        }, onError);
      }

      var permission = window.Notification.permission;
      if (permission === "default") {
        window.Notification.requestPermission().then(subscribe, onError);
      } else {
        subscribe(permission);
      }
    }

    /* La baja remota va primero para no perder el único endpoint que permite
       limpiarla. Si falla, se guarda para reintento y luego se completa la baja
       local: el usuario no debe seguir viendo una suscripción que quiso quitar. */
    function drop(sub, onSuccess, onError) {
      var endpoint = sub.endpoint;

      function finishLocal() {
        sub.unsubscribe().then(function () {
          activeSubscription = null;
          onSuccess(false);
        }, onError);
      }

      post("/api/unsubscribe/", { endpoint: endpoint }, function () {
        forgetRetry(endpoint);
        finishLocal();
      }, function () {
        rememberRetry(endpoint);
        finishLocal();
      });
    }

    function revalidate(reg, onSuccess, onError) {
      reg.pushManager.getSubscription().then(function (sub) {
        activeSubscription = sub;
        if (!sub) {
          onSuccess(false);
          return;
        }
        if (keyMatches(sub)) {
          revalidateRemote(sub, onSuccess, onError);
          return;
        }
        drop(sub, function () {
          add(reg, onSuccess, onError);
        }, onError);
      }, onError);
    }

    if (!API || !vapidBytes()) {
      btn.hidden = true;
      say("La configuración de avisos no está disponible.");
      return;
    }

    if (!supported()) {
      btn.hidden = true;
      say(iosNeedsInstall()
        ? "En iPhone y iPad hay que agregar el sitio a la pantalla de inicio (Compartir → Agregar a inicio) para recibir avisos."
        : "Este navegador no admite avisos. También podés seguir las notas por RSS.");
      return;
    }

    if (window.Notification.permission === "denied") {
      btn.hidden = true;
      say("Los avisos están bloqueados para este sitio. Se reactivan desde la configuración de notificaciones del navegador.");
      return;
    }

    btn.hidden = false;
    renderLoading("verify", false);
    operationPending = true;

    navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function (reg) {
      revalidate(reg, function (on) {
        render(on);
        operationPending = false;
        btn.disabled = false;

        btn.addEventListener("click", function () {
          if (operationPending) return;
          operationPending = true;

          var currentlyOn = activeSubscription !== null;
          renderLoading(currentlyOn ? "drop" : "add", currentlyOn);

          function complete(nextOn) {
            render(nextOn);
            operationPending = false;
            btn.disabled = false;
          }

          function fail(error) {
          render(false);
          say("No se pudo completar la operación: " +
            (error && error.message ? error.message : "error desconocido") + ".");
            operationPending = false;
            btn.disabled = false;
          }

          if (activeSubscription) {
            drop(activeSubscription, complete, fail);
          } else {
            add(reg, complete, fail);
          }
        });
      }, function () {
        btn.hidden = true;
        say("No se pudo iniciar el servicio de avisos.");
        operationPending = false;
        btn.disabled = false;
      });
    }, function () {
      btn.hidden = true;
      say("No se pudo iniciar el servicio de avisos.");
      operationPending = false;
      btn.disabled = false;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

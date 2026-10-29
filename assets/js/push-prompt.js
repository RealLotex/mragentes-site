/* Invitación visual. El alta y su confirmación siguen siendo de push.js. */
(function () {
  "use strict";
  var initialized = false;
  var DISMISS_KEY = "mragentes:push-prompt-dismissed";
  var SESSION_KEY = "mragentes:push-prompt-seen";
  var WEEK = 7 * 24 * 60 * 60 * 1000;

  function init() {
    if (initialized) return;
    initialized = true;
    var panel = document.querySelector("[data-push-prompt]");
    var footer = document.querySelector("[data-push-btn]");
    if (!panel || !footer) return;
    var activate = panel.querySelector("[data-push-prompt-activate]");
    var activateLabel = panel.querySelector("[data-push-prompt-label]");
    var status = panel.querySelector("[data-push-prompt-status]");
    var footerStatus = document.querySelector("[data-push-status]");
    if (!activate || !activateLabel || !status) return;

    var timer = null;
    var wasShown = false;
    var wasActive = false;
    var activationRequested = false;
    var previousFocus = null;

    function read(storage, key) {
      try { return window[storage].getItem(key); } catch (_error) { return null; }
    }
    function write(storage, key, value) {
      try { window[storage].setItem(key, value); } catch (_error) {}
    }
    function suppressed() {
      var dismissed = Number(read("localStorage", DISMISS_KEY));
      var elapsed = Date.now() - dismissed;
      return read("sessionStorage", SESSION_KEY) === "1" ||
        (dismissed > 0 && elapsed >= 0 && elapsed < WEEK);
    }
    function allowed() {
      return typeof window.Notification !== "undefined" &&
        window.Notification.permission !== "denied" &&
        !footer.hidden && !footer.disabled &&
        footer.getAttribute("aria-pressed") === "false" && !wasActive;
    }
    function cancelTimer() {
      if (timer !== null) window.clearTimeout(timer);
      timer = null;
    }
    function hide() {
      var restore = panel.contains(document.activeElement);
      panel.hidden = true;
      cancelTimer();
      if (restore && previousFocus && previousFocus !== document.body &&
          document.contains(previousFocus) && typeof previousFocus.focus === "function") {
        previousFocus.focus({ preventScroll: true });
      }
    }
    function dismiss() {
      write("localStorage", DISMISS_KEY, String(Date.now()));
      hide();
    }
    function sync() {
      if (footer.getAttribute("aria-pressed") === "true") {
        wasActive = true;
        write("sessionStorage", SESSION_KEY, "1");
        hide();
        return;
      }
      if (typeof window.Notification === "undefined" ||
          window.Notification.permission === "denied" || footer.hidden) {
        hide();
        return;
      }
      if (!panel.hidden) {
        activate.disabled = footer.disabled;
        activateLabel.textContent = footer.disabled ? "Activando avisos…" : "Activar notificaciones";
        panel.setAttribute("aria-busy", String(footer.disabled));
        status.textContent = activationRequested && footerStatus ? footerStatus.textContent : "";
        return;
      }
      if (!allowed() || wasShown || suppressed() || document.hidden) {
        cancelTimer();
        return;
      }
      if (timer === null) {
        timer = window.setTimeout(function () {
          timer = null;
          if (!allowed() || wasShown || suppressed() || document.hidden) return;
          previousFocus = document.activeElement;
          wasShown = true;
          write("sessionStorage", SESSION_KEY, "1");
          panel.hidden = false;
        }, 10000);
      }
    }

    panel.querySelectorAll("[data-push-prompt-dismiss]").forEach(function (button) {
      button.addEventListener("click", dismiss);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !panel.hidden) dismiss();
    });
    activate.addEventListener("click", function () {
      if (panel.hidden || !allowed()) return;
      activationRequested = true;
      footer.click();
      sync();
    });
    document.addEventListener("visibilitychange", sync);
    var observer = new MutationObserver(sync);
    observer.observe(footer, { attributes: true, attributeFilter: ["hidden", "disabled", "aria-pressed"] });
    if (footerStatus) observer.observe(footerStatus, { childList: true, characterData: true, subtree: true });
    sync();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

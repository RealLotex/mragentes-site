import { describe, expect, test, vi } from "vitest";
import { JSDOM } from "jsdom";

import { initReadAloud, speechParts } from "../assets/js/note-reading.js";

const argentina = { lang: "es-AR", localService: true };
const spain = { lang: "es-ES", localService: true };
const remote = { lang: "es-AR", localService: false };

function reader(voices) {
  const dom = new JSDOM(`
    <article><h1>Una nota</h1>
    <button data-note-audio hidden><span data-audio-duration>02:30</span></button>
    <section data-note-player hidden>
      <button data-audio-toggle><span data-audio-play></span><span data-audio-pause hidden></span></button>
      <button data-audio-skip="-15"></button><button data-audio-skip="15"></button>
      <input type="range" data-audio-progress min="0" max="150" value="0">
      <span data-audio-current>00:00</span><p data-audio-error></p>
    </section>
    <div data-note-text>Primera frase. Segunda frase. ${"uno dos tres cuatro cinco ".repeat(80)}</div></article>`);
  const speak = vi.fn();
  const cancel = vi.fn();
  dom.window.speechSynthesis = { getVoices: () => voices, speak, cancel };
  dom.window.SpeechSynthesisUtterance = class {
    constructor(text) { this.text = text; }
  };
  const root = dom.window.document.querySelector("article");
  initReadAloud(root, dom.window);
  return { dom, button: root.querySelector("[data-note-audio]"), player: root.querySelector("[data-note-player]"), speak, cancel };
}

describe("Lectura en voz alta de una nota", () => {
  test("prefiere español argentino local, encadena frases y permite pausar y reanudar", () => {
    const { dom, button, player, speak, cancel } = reader([remote, spain, argentina]);
    try {
      expect(button.hidden).toBe(false);
      button.click();
      expect(player.hidden).toBe(false);
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ voice: argentina, lang: "es-AR", text: "Una nota." }));
      speak.mock.lastCall[0].onend();
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ voice: argentina, text: "Primera frase." }));
      const interrupted = speak.mock.lastCall[0];
      const toggle = player.querySelector("[data-audio-toggle]");
      expect(toggle.getAttribute("aria-label")).toBe("Pausar lectura");
      toggle.click();
      expect(cancel).toHaveBeenCalledOnce();
      interrupted.onend();
      expect(speak).toHaveBeenCalledTimes(2);
      expect(toggle.getAttribute("aria-label")).toBe("Reproducir lectura");
      toggle.click();
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: "Primera frase." }));
    } finally { dom.window.close(); }
  });

  test("deja el contenido en el dispositivo aunque la única voz en español sea remota", () => {
    const { dom, button, player, speak } = reader([remote, { lang: "en-GB", localService: true }]);
    try {
      button.click();
      expect(speak).not.toHaveBeenCalled();
      expect(player.querySelector("[data-audio-error]").textContent).toMatch(/voz en español/);
    } finally { dom.window.close(); }
  });

  test("permite mover la barra y navegar de a 15 segundos aún en pausa", () => {
    const { dom, button, player, speak } = reader([spain]);
    try {
      button.click();
      const progress = player.querySelector("[data-audio-progress]");
      const toggle = player.querySelector("[data-audio-toggle]");
      const elapsed = player.querySelector("[data-audio-current]");
      player.querySelector('[data-audio-skip="15"]').click();
      expect(elapsed.textContent).toBe("00:15");
      expect(speak.mock.lastCall[0]).toMatchObject({ lang: "es-ES" });
      toggle.click();
      const calls = speak.mock.calls.length;
      player.querySelector('[data-audio-skip="-15"]').click();
      expect(elapsed.textContent).toBe("00:00");
      progress.value = "24";
      progress.dispatchEvent(new dom.window.Event("input"));
      expect(elapsed.textContent).toBe("00:24");
      progress.dispatchEvent(new dom.window.Event("change"));
      expect(speak).toHaveBeenCalledTimes(calls);
      toggle.click();
      expect(speak.mock.lastCall[0].text).toMatch(/uno|dos|tres|cuatro|cinco/);
      expect(elapsed.textContent).toBe("00:24");
    } finally { dom.window.close(); }
  });

  test("trocea texto largo sin perder palabras y respeta números con puntos", () => {
    const text = `US$81.340 millones. ${"inteligencia artificial ".repeat(40).trim()}.`;
    const parts = speechParts(text);
    expect(parts[0]).toBe("US$81.340 millones.");
    expect(parts.every((part) => part.length <= 240)).toBe(true);
    expect(parts.join(" ")).toBe(text);
  });
});

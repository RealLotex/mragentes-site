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
    <div data-note-text>Primera frase. Segunda frase.</div></article>`);
  const speak = vi.fn();
  const cancel = vi.fn();
  const tell = vi.fn();
  dom.window.speechSynthesis = { getVoices: () => voices, speak, cancel };
  dom.window.SpeechSynthesisUtterance = class {
    constructor(text) { this.text = text; }
  };
  const root = dom.window.document.querySelector("article");
  initReadAloud(root, tell, dom.window);
  return { dom, button: root.querySelector("button"), speak, cancel, tell };
}

describe("Lectura en voz alta de una nota", () => {
  test("prefiere español argentino local, encadena frases y se puede detener", () => {
    const { dom, button, speak, cancel, tell } = reader([remote, spain, argentina]);
    try {
      expect(button.hidden).toBe(false);
      button.click();
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ voice: argentina, text: "Una nota." }));
      speak.mock.lastCall[0].onend();
      expect(speak).toHaveBeenCalledWith(expect.objectContaining({ voice: argentina, text: "Primera frase." }));
      button.click();
      expect(cancel).toHaveBeenCalledOnce();
      expect(button.getAttribute("aria-pressed")).toBe("false");
      expect(button.getAttribute("aria-label")).toContain("02:30");
      expect(tell).toHaveBeenLastCalledWith("Lectura detenida.");
    } finally { dom.window.close(); }
  });

  test("deja el contenido en el dispositivo aunque la única voz en español sea remota", () => {
    const { dom, button, speak, tell } = reader([remote, { lang: "en-GB", localService: true }]);
    try {
      button.click();
      expect(speak).not.toHaveBeenCalled();
      expect(tell.mock.lastCall[0]).toMatch(/voz en español/);
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

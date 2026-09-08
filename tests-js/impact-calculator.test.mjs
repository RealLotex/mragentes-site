import { describe, expect, test } from "vitest";
import { JSDOM } from "jsdom";

import { importPlannedModule } from "./support/target-loader.mjs";

const TRACE = "IMPACT-CALCULATOR";

async function calculator() {
  const target = await importPlannedModule(["assets/js/impact-calculator.js"], TRACE);
  return target.module;
}

describe("calculadora de impacto", () => {
  test("[IMPACT-CALCULATOR-001] calcula tiempo, costo y errores con supuestos explícitos", async () => {
    const { calculateImpact } = await calculator();
    const result = calculateImpact({
      weeklyVolume: 25, manualMinutes: 12, automatedMinutes: 4, hourlyCost: 7000,
      manualErrorRate: 8, errorReduction: 60, costPerError: 7000,
    });
    expect(result.monthlyCases).toBe(108.3);
    expect(result.savedHours).toBe(14.4);
    expect(result.operatingSavings).toBe(101033);
    expect(result.errorsAvoided).toBe(5.2);
    expect(result.errorSavings).toBe(36372);
    expect(result.totalPotential).toBe(137405);
    expect(result.controls).toContain("Registro de cada ejecución, responsable y resultado.");
  });

  test("[IMPACT-CALCULATOR-002] no inventa ahorros negativos y limita porcentajes inválidos", async () => {
    const { calculateImpact } = await calculator();
    const result = calculateImpact({
      weeklyVolume: 10, manualMinutes: 3, automatedMinutes: 7, hourlyCost: -1,
      manualErrorRate: 500, errorReduction: 900, costPerError: -20,
    });
    expect(result.savedHours).toBe(0);
    expect(result.operatingSavings).toBe(0);
    expect(result.errorSavings).toBe(0);
    expect(result.totalPotential).toBe(0);
    expect(result.controls[0]).toMatch(/aún no reduce tiempo/i);
  });

  test("[IMPACT-CALCULATOR-003] muestra resultados cuando el panel es hermano del formulario", async () => {
    const dom = new JSDOM(`<!doctype html><body>
      <section class="impact-calculator">
        <form data-impact-calculator>
          <input name="weekly_volume" value="25">
          <input name="manual_minutes" value="12">
          <input name="automated_minutes" value="4">
          <input name="hourly_cost" value="7000">
          <input name="manual_error_rate" value="8">
          <input name="error_reduction" value="60">
          <input name="cost_per_error" value="7000">
        </form>
        <aside data-impact-results>
          <span data-impact-hours>—</span><span data-impact-operating>—</span>
          <span data-impact-errors>—</span><span data-impact-total>—</span>
          <ul data-impact-controls></ul>
        </aside>
      </section>
    </body>`, { url: "https://mragentes.com.ar/herramientas/" });
    const previousDocument = globalThis.document;
    const previousWindow = globalThis.window;
    globalThis.document = dom.window.document;
    globalThis.window = dom.window;

    try {
      const { initImpactCalculator } = await calculator();
      initImpactCalculator(dom.window.document);
      expect(dom.window.document.querySelector("[data-impact-hours]").textContent).toBe("14,4 h");
      expect(dom.window.document.querySelectorAll("[data-impact-controls] li")).toHaveLength(4);
    } finally {
      globalThis.document = previousDocument;
      globalThis.window = previousWindow;
      dom.window.close();
    }
  });
});

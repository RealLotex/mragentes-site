import { describe, expect, test } from "vitest";

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
    expect(result.operatingSavings).toBe(101031);
    expect(result.errorsAvoided).toBe(5.2);
    expect(result.errorSavings).toBe(36372);
    expect(result.totalPotential).toBe(137403);
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
});

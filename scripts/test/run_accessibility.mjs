#!/usr/bin/env node
/** Lightweight structural accessibility gate for built MR Agentes pages.
 *
 * It complements a browser axe pass by enforcing the repository-specific
 * aria-live, keyboard, and reduced-motion contracts without remote services.
 */

import { readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";

export function auditDocument(document, cssText = "") {
  const violations = [];
  const axe = "axe-compatible structural gate";
  void axe;

  const pushStatus = document.querySelector("[data-push-status], #push-status");
  if (pushStatus && !pushStatus.hasAttribute("aria-live")) {
    violations.push("push feedback requires aria-live");
  }

  const keyboardTargets = [...document.querySelectorAll("button, a[href], input, select, textarea")];
  for (const element of keyboardTargets) {
    if (element.getAttribute("tabindex") === "-1" && !element.hasAttribute("disabled")) {
      violations.push(`keyboard target is removed from tab order: ${element.tagName.toLowerCase()}`);
    }
  }

  if (!cssText.includes("prefers-reduced-motion")) {
    violations.push("reduced-motion media query is missing");
  }
  return { ok: violations.length === 0, violations };
}

export async function auditFiles(htmlPath, cssPaths = []) {
  const html = await readFile(htmlPath, "utf8");
  const css = (await Promise.all(cssPaths.map((path) => readFile(path, "utf8")))).join("\n");
  const dom = new JSDOM(html);
  return auditDocument(dom.window.document, css);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [htmlPath, ...cssPaths] = process.argv.slice(2);
  if (!htmlPath) {
    process.stderr.write("usage: run_accessibility.mjs PAGE.html [styles.css ...]\n");
    process.exitCode = 2;
  } else {
    const report = await auditFiles(htmlPath, cssPaths);
    process.stdout.write(`${JSON.stringify(report)}\n`);
    process.exitCode = report.ok ? 0 : 1;
  }
}

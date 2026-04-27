#!/usr/bin/env node
/*
 * Repository: azure-naming
 * Path: extensions/confluence/scripts/capture-confluence-screenshots.mjs
 * Purpose: Capture rendered screenshots of one or more Confluence Cloud
 *          pages (typically pages embedding the claim-name-macro) using
 *          REST + Playwright. Auth is HTTP Basic with email + Atlassian
 *          API token.
 * Author: SanMar Platform Team
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 1.0.0
 *
 * Required env vars:
 *   CONFLUENCE_BASE_URL   e.g. https://sanmar.atlassian.net
 *   CONFLUENCE_EMAIL      Atlassian account email
 *   CONFLUENCE_API_KEY    Atlassian API token (id.atlassian.com/manage-profile/security/api-tokens)
 *   CONFLUENCE_PAGE_IDS   comma-separated Confluence page IDs
 *
 * Optional env vars:
 *   OUTPUT_DIR            output directory (default: ./screenshots)
 *   VIEWPORT_WIDTH        default 1440
 *   VIEWPORT_HEIGHT       default 900
 *
 * Output:
 *   <OUTPUT_DIR>/page-<id>.html   wrapped export_view HTML
 *   <OUTPUT_DIR>/page-<id>.png    full-page screenshot
 *   <OUTPUT_DIR>/manifest.json    capture summary
 */

import { mkdir, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { chromium } from "@playwright/test";

const REQUIRED = [
  "CONFLUENCE_BASE_URL",
  "CONFLUENCE_EMAIL",
  "CONFLUENCE_API_KEY",
  "CONFLUENCE_PAGE_IDS",
];

for (const k of REQUIRED) {
  if (!process.env[k]) {
    console.error(`[capture] missing required env: ${k}`);
    process.exit(2);
  }
}

const base = process.env.CONFLUENCE_BASE_URL.replace(/\/+$/, "");
const email = process.env.CONFLUENCE_EMAIL;
const token = process.env.CONFLUENCE_API_KEY;
const auth = "Basic " + Buffer.from(`${email}:${token}`).toString("base64");
const ids = process.env.CONFLUENCE_PAGE_IDS.split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const outDir = process.env.OUTPUT_DIR || "./screenshots";
const width = parseInt(process.env.VIEWPORT_WIDTH || "1440", 10);
const height = parseInt(process.env.VIEWPORT_HEIGHT || "900", 10);

await mkdir(outDir, { recursive: true });

const wrap = (title, body) => `<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; color: #172B4D; background: #fff; margin: 0; padding: 32px; }
  .page { max-width: 960px; margin: 0 auto; }
  h1, h2, h3, h4 { color: #172B4D; line-height: 1.25; }
  h1 { font-size: 28px; margin-top: 0; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  th, td { border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left; vertical-align: top; }
  th { background: #F4F5F7; }
  code, pre { font-family: "SFMono-Regular", Menlo, Consolas, monospace; background: #F4F5F7; border-radius: 3px; }
  code { padding: 1px 4px; }
  pre { padding: 12px; overflow-x: auto; }
  .confluence-information-macro { border: 1px solid #DFE1E6; border-radius: 3px; padding: 12px; margin: 12px 0; background: #F4F5F7; }
  .confluence-information-macro-information { background: #DEEBFF; border-color: #B3D4FF; }
  .confluence-information-macro-warning { background: #FFFAE6; border-color: #FFE380; }
  .confluence-information-macro-note { background: #EAE6FF; border-color: #C0B6F2; }
  blockquote { border-left: 4px solid #DFE1E6; margin: 12px 0; padding: 0 12px; color: #5E6C84; }
</style>
</head><body><div class="page">${body}</div></body></html>`;

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width, height },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();

const captured = [];
const failed = [];

for (const id of ids) {
  const url = `${base}/wiki/rest/api/content/${id}?expand=body.export_view,title,space,version`;
  console.log(`[capture] GET ${url}`);
  let response;
  try {
    response = await fetch(url, {
      headers: { Authorization: auth, Accept: "application/json" },
    });
  } catch (err) {
    console.error(`[capture] page ${id}: fetch error: ${err.message}`);
    failed.push({ id, error: err.message });
    process.exitCode = 1;
    continue;
  }
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    console.error(`[capture] page ${id}: HTTP ${response.status} ${body.slice(0, 200)}`);
    failed.push({ id, status: response.status });
    process.exitCode = 1;
    continue;
  }
  const data = await response.json();
  const title = data.title || `page-${id}`;
  const html = wrap(title, data.body?.export_view?.value || "<p>(empty)</p>");
  const htmlPath = resolve(outDir, `page-${id}.html`);
  const pngPath = resolve(outDir, `page-${id}.png`);
  await writeFile(htmlPath, html, "utf8");
  await page.goto("file://" + htmlPath, { waitUntil: "networkidle" });
  await page.screenshot({ path: pngPath, fullPage: true });
  console.log(`[capture] page ${id} (${title}) -> ${pngPath}`);
  captured.push({
    id,
    title,
    space: data.space?.key,
    version: data.version?.number,
    html: htmlPath,
    png: pngPath,
  });
}

await writeFile(
  join(outDir, "manifest.json"),
  JSON.stringify(
    {
      generatedAt: new Date().toISOString(),
      base,
      viewport: { width, height },
      captured,
      failed,
    },
    null,
    2,
  ),
);

await browser.close();

if (failed.length) {
  console.error(`[capture] ${failed.length} page(s) failed; see manifest.json`);
}
console.log(`[capture] captured ${captured.length} page(s) into ${outDir}`);

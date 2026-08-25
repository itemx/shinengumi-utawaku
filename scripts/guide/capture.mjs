/**
 * 產生使用說明用的截圖與 PDF（headless Chrome + CDP，零額外相依）。
 *
 * 用法（需先啟動 dev server 或 preview server）：
 *   node scripts/guide/capture.mjs [baseUrl]
 *
 * 產出：
 *   public/guide/*.png   — 說明頁用的截圖
 *   local/setlist-guide.pdf — 本地確認用の PDF（発布しない）
 */
import { spawn, execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, unlinkSync, renameSync, statSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const BASE = process.argv[2] || "http://localhost:4321";
const OUT = "public/guide";      // 截圖：網頁要用，會發布
const PDF_OUT = "local";         // PDF：本地確認用，不發布（.gitignore 済み）
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9333;

mkdirSync(OUT, { recursive: true });
mkdirSync(PDF_OUT, { recursive: true });

// --- 啟動 headless Chrome ---
const chrome = spawn(CHROME, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  "--hide-scrollbars",
  "--no-first-run",
  "--no-default-browser-check",
  "--user-data-dir=/tmp/utalist-guide-profile",
  "about:blank",
], { stdio: "ignore" });

process.on("exit", () => chrome.kill());

// --- CDP 連線（browser target → 建立 page target → attach） ---
async function browserWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const v = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
      if (v.webSocketDebuggerUrl) return v.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error("Chrome DevTools への接続に失敗しました");
}

const ws = new WebSocket(await browserWs());
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let msgId = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) {
    const { resolve, reject } = pending.get(m.id);
    pending.delete(m.id);
    m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
  }
};

let sessionId = null;
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    const msg = { id, method, params };
    if (sessionId) msg.sessionId = sessionId;
    ws.send(JSON.stringify(msg));
  });

// page target を作って attach（flatten でセッション経由に統一）
const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const attached = await send("Target.attachToTarget", { targetId, flatten: true });
sessionId = attached.sessionId;

const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", {
    expression: `(async () => { ${expr} })()`,
    awaitPromise: true,
    returnByValue: true,
  });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " + (r.exceptionDetails.exception?.description ?? ""));
  return r.result.value;
};

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 1280, height: 900, deviceScaleFactor: 2, mobile: false,
});

async function goto(url) {
  await send("Page.navigate", { url });
  await sleep(1600); // 等 Astro hydrate + inline script 跑完
}

/** 截圖指定選擇器的區塊（含一點留白） */
async function shot(name, selector, pad = 10) {
  const box = await evaluate(`
    var el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return null;
    el.scrollIntoView({block:'center'});
    await new Promise(r=>setTimeout(r,250));
    var r = el.getBoundingClientRect();
    // captureBeyondViewport はページ座標を使うため、スクロール量を足す
    return {x:r.x + window.scrollX, y:r.y + window.scrollY, w:r.width, h:r.height};
  `);
  if (!box) { console.log(`  ⚠ ${name}: 找不到 ${selector}`); return; }
  const clip = {
    x: Math.max(0, box.x - pad),
    y: Math.max(0, box.y - pad),
    width: box.w + pad * 2,
    height: box.h + pad * 2,
    scale: 1.5,
  };
  const { data } = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, "base64"));
  console.log(`  ✓ ${name}.png  (${Math.round(clip.width)}×${Math.round(clip.height)})`);
}

// 日本語表示に固定
await goto(`${BASE}/plan`);
await evaluate(`document.cookie = "vutalist-lang=ja;path=/;max-age=31536000";`);
await goto(`${BASE}/plan`);

console.log("截圖中…");

// ① 全体
await shot("01-overview", ".grid.md\\:grid-cols-\\[1fr_320px\\]", 4);

// ② チャンネル絞り込み
await evaluate(`
  var sel=document.getElementById('channel');
  sel.value=[...sel.options].find(o=>o.textContent.includes('渉海'))?.value || sel.value;
  sel.dispatchEvent(new Event('change'));
  await new Promise(r=>setTimeout(r,300));
`);
await shot("02-channel", "#filters", 10);

// ③ タグ絞り込み（アニメ）
await evaluate(`
  var sel=document.getElementById('channel'); sel.value=''; sel.dispatchEvent(new Event('change'));
  var chip=[...document.querySelectorAll('.tag-chip')].find(b=>b.dataset.tag==='anime');
  chip.click();
  await new Promise(r=>setTimeout(r,300));
`);
await shot("03-tags", "#tagbar", 8);

// ④ 検索で絞り込み（ヨルシカ）
await evaluate(`
  var chip=[...document.querySelectorAll('.tag-chip')].find(b=>b.dataset.tag==='anime');
  chip.click();
  var q=document.getElementById('q'); q.value='ヨルシカ'; q.dispatchEvent(new Event('input'));
  await new Promise(r=>setTimeout(r,400));
`);
await shot("04-search", "#pool", 8);

// ⑤ 選択中リスト（並べ替え）
await evaluate(`
  var rows=[...document.querySelectorAll('#pool li')];
  rows[0].click(); rows[1].click(); rows[2].click(); rows[3].click();
  var q=document.getElementById('q'); q.value=''; q.dispatchEvent(new Event('input'));
  await new Promise(r=>setTimeout(r,400));
`);
await shot("05-selected", "#selected", 12);

// ⑥ 時間指定で自動編成
await evaluate(`
  document.getElementById('clear').click();
  var t=document.getElementById('target'); t.value='60'; t.dispatchEvent(new Event('input'));
  document.getElementById('autofill').click();
  await new Promise(r=>setTimeout(r,400));
`);
await shot("06-autofill", ".md\\:sticky", 8);

// ⑦ 書き出しモーダル
await evaluate(`
  document.getElementById('open-out').click();
  await new Promise(r=>setTimeout(r,400));
`);
await shot("07-export", "#out-modal > div", 8);

// ⑧ フッターの入口
await goto(`${BASE}/`);
await shot("08-entry", "footer", 4);

// --- PDF ---
console.log("PDF 產生中…");
await goto(`${BASE}/guide`);
const pdf = await send("Page.printToPDF", {
  printBackground: true,
  paperWidth: 8.27,   // A4
  paperHeight: 11.69,
  marginTop: 0.6, marginBottom: 0.6, marginLeft: 0.5, marginRight: 0.5,
  preferCSSPageSize: false,
});
const rawPdf = `${PDF_OUT}/setlist-guide.raw.pdf`;
const finalPdf = `${PDF_OUT}/setlist-guide.pdf`;
writeFileSync(rawPdf, Buffer.from(pdf.data, "base64"));

// Chrome は画像を非圧縮で埋め込むため Ghostscript で圧縮（あれば）
try {
  execFileSync("gs", [
    "-sDEVICE=pdfwrite",
    "-dCompatibilityLevel=1.5",
    "-dPDFSETTINGS=/ebook",     // 150dpi 相当。UI スクショには十分
    "-dNOPAUSE", "-dQUIET", "-dBATCH",
    "-dDetectDuplicateImages=true",
    `-sOutputFile=${finalPdf}`, rawPdf,
  ]);
  unlinkSync(rawPdf);
} catch {
  // gs が無ければ非圧縮版をそのまま使う
  renameSync(rawPdf, finalPdf);
  console.log("  （gs 未検出のため未圧縮）");
}
const kb = Math.round(statSync(finalPdf).size / 1024);
console.log(`  ✓ setlist-guide.pdf  (${kb} KB)`);

ws.close();
chrome.kill();
console.log("完了");
process.exit(0);

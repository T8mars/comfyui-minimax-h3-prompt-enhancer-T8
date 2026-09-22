// Wait for the real asynchronous browser harness to finish instead of trusting
// Chromium's --dump-dom timing under a virtual-time budget.
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const [browser, url, screenshotPath = ""] = process.argv.slice(2);
if (!browser || !url) throw new Error("Usage: node frontend_browser_cdp.mjs BROWSER URL [SCREENSHOT]");
const profile = await mkdtemp(join(tmpdir(), "t8-browser-cdp-"));
const chrome = spawn(browser, [
  "--headless=new", "--disable-gpu", "--disable-extensions",
  "--disable-background-networking", "--no-first-run",
  "--remote-debugging-port=0", "--remote-allow-origins=*",
  `--user-data-dir=${profile}`, url,
], { stdio: "ignore" });
const deadline = Date.now() + 30000;
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket;

async function connect() {
  let port;
  while (!port && Date.now() < deadline) {
    if (chrome.exitCode !== null) throw new Error(`Chromium exited before DevTools opened (${chrome.exitCode})`);
    try { port = Number((await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]); }
    catch { await pause(100); }
  }
  if (!port) throw new Error("Timed out waiting for Chromium DevTools port");
  let target;
  while (!target && Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const pages = await response.json();
      target = pages.find(page => page.type === "page" && page.url === url) || pages.find(page => page.type === "page");
    } catch { /* The port file can precede the HTTP listener. */ }
    if (!target) await pause(100);
  }
  if (!target) throw new Error("Timed out waiting for browser page");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((done, fail) => {
    socket.addEventListener("open", done, { once: true });
    socket.addEventListener("error", fail, { once: true });
  });
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener("message", event => {
    const response = JSON.parse(event.data);
    if (!response.id || !pending.has(response.id)) return;
    const { done, fail } = pending.get(response.id);
    pending.delete(response.id);
    response.error ? fail(new Error(response.error.message)) : done(response.result);
  });
  return (method, params = {}) => new Promise((done, fail) => {
    const id = ++nextId;
    pending.set(id, { done, fail });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

try {
  const send = await connect();
  let result;
  while (Date.now() < deadline) {
    const evaluation = await send("Runtime.evaluate", {
      expression: "JSON.stringify({status:document.querySelector('#result')?.dataset.status || '',text:document.querySelector('#result')?.textContent || ''})",
      returnByValue: true,
    });
    if (evaluation.exceptionDetails) throw new Error("Browser status evaluation failed");
    result = JSON.parse(evaluation.result.value);
    if (result.status === "pass" || result.status === "fail") break;
    await pause(100);
  }
  if (!result || !["pass", "fail"].includes(result.status)) throw new Error(`Browser harness did not finish: ${result?.text || "no result"}`);
  if (result.status === "fail") throw new Error(result.text);
  if (screenshotPath) {
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    await writeFile(resolve(screenshotPath), Buffer.from(shot.data, "base64"));
  }
  process.stdout.write(result.text + "\n");
} catch (error) {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
} finally {
  socket?.close();
  chrome.kill();
  if (resolve(profile).startsWith(resolve(tmpdir(), "t8-browser-cdp-"))) {
    await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
  }
}

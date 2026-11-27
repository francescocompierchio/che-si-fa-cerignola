const { chromium } = require("playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ serviceWorkers: "allow" });
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("dialog", dialog => dialog.accept());
    await page.addInitScript(() => {
      window.segnalazioniTest = [];
      window.firebase = {
        initializeApp() {},
        database: () => ({
          ref: path => ({
            on() {},
            push: async value => {
              if (path === "segnalazioniDaApprovare") window.segnalazioniTest.push(value);
            }
          })
        })
      };
    });
    await page.route("**/*", route => route.request().url().startsWith("http://127.0.0.1:8765/") ? route.continue() : route.abort());
    await page.goto("http://127.0.0.1:8765/index.html");
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
    await page.locator("#btn-segnala-evento").click();
    await page.locator("#seg-social").click();
    assert.ok(await page.locator("#seg-rapida").isVisible());
    assert.ok(await page.locator("#form-segnalazione-pubblica").isHidden());
    assert.ok(await page.locator("#quick-invia").isDisabled());
    const date = new Date(Date.now() + 4 * 86400000).toISOString().slice(0, 10);
    const text = ["Evento: DJ Set di prova", "Locale: Sala di prova", "Comune: Cerignola", "Data: "+date, "Ore 22:30"].join("\n");
    const source = "https://www.instagram.com/reel/AbCd1234/?igsh=tracking";
    await page.locator("#quick-link").fill(source);
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    let first=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(first.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(first.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.ok(!first.dataInizio&&!first.citta&&!first.luogo);
    assert.ok(!first.screenshot);
    await page.locator("#quick-foto").setInputFiles({name:"screenshot.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==","base64")});
    await page.locator("#quick-preview").waitFor({state:"visible"});
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===2);
    const second=await page.evaluate(()=>window.segnalazioniTest[1]);
    assert.ok(second.screenshot.startsWith("data:image/jpeg;base64,"));
    assert.ok(second.screenshot.length<=240000);
    assert.equal(second.fonteUrl,"");
    assert.ok(!second.dataInizio&&!second.citta);
    await Promise.all([
      page.waitForNavigation(),
      page.evaluate(({source,text}) => {
        const form = document.createElement("form");
        form.method = "post";
        form.enctype = "multipart/form-data";
        form.action = "index.html?ricevi-social=1";
        for (const [name, value] of Object.entries({fonte:source, testo:text})) {
          const field = document.createElement("textarea");
          field.name = name;
          field.value = value;
          form.append(field);
        }
        const attachment = document.createElement("input");
        attachment.type = "file";
        attachment.name = "foto";
        const transfer = new DataTransfer();
        const bytes = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg=="), c => c.charCodeAt(0));
        transfer.items.add(new File([bytes], "prova.png", {type:"image/png"}));
        attachment.files = transfer.files;
        form.append(attachment);
        document.body.append(form);
        form.submit();
      }, {source,text})
    ]);
    await page.waitForFunction(() => document.querySelector("#quick-link").value.includes("/reel/AbCd1234/"));
    await page.locator("#quick-preview").waitFor({state:"visible"});
    assert.ok(await page.locator("#seg-rapida").isVisible());
    assert.ok(await page.locator("#form-segnalazione-pubblica").isHidden());
    assert.equal(new URL(page.url()).search,"");
    assert.equal(await page.evaluate(async () => (await (await caches.open("chesifa-social-local-v1")).keys()).length),0);
    assert.equal(await page.evaluate(() => window.segnalazioniTest.length),0);
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    const sent=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(sent.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(sent.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.ok(sent.screenshot.startsWith("data:image/jpeg;base64,"));
    assert.ok(!sent.dataInizio&&!sent.citta);
    assert.ok(!JSON.stringify(sent).includes("prova.png"));
    assert.deepEqual(errors, []);
    console.log("OK segnalazioni rapide: link solo, screenshot solo, share target con foto, bozza consumata e invio esplicito.");
  } finally {
    await browser.close();
  }
})().catch(err => {console.error(err); process.exitCode = 1;});

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
    assert.ok(await page.locator("#seg-contatto-wrap").isHidden());
    assert.equal(await page.locator("#seg-contatto").evaluate(el => el.required), false);
    assert.equal(await page.locator("#seg-data").inputValue(), "");
    assert.equal(await page.locator("#seg-citta").inputValue(), "");
    assert.equal(await page.locator("#seg-autorizzato").isChecked(), false);

    await page.locator("#seg-social-testo summary").click();
    const date = new Date(Date.now() + 4 * 86400000).toISOString().slice(0, 10);
    const text = ["Evento: DJ Set di prova", "Locale: Sala di prova", "Comune: Cerignola", "Data: "+date, "Ore 22:30"].join("\n");
    const source = "https://www.instagram.com/reel/AbCd1234/?igsh=tracking";
    await page.locator("#seg-social-incolla").fill(text+"\n"+source);
    await page.locator("#seg-social-applica").click();
    assert.equal(await page.locator("#seg-titolo").inputValue(), "DJ Set di prova");
    assert.equal(await page.locator("#seg-data").inputValue(), date);
    assert.equal(await page.locator("#seg-ora").inputValue(), "Ore 22:30");
    assert.equal(await page.locator("#seg-citta").inputValue(), "Cerignola");
    assert.equal(await page.locator("#seg-fonte").inputValue(), "https://www.instagram.com/reel/AbCd1234/");

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
    await page.waitForFunction(() => document.querySelector("#seg-fonte").value.includes("/reel/AbCd1234/"));
    assert.ok(await page.locator("#form-segnalazione-pubblica").isVisible());
    assert.equal(await page.locator("#seg-autorizzato").isChecked(),false);
    assert.equal(await page.locator("#seg-data").inputValue(),date);
    assert.match(await page.locator("#seg-poster-status").textContent(), /Locandina pronta/);
    assert.equal(new URL(page.url()).search,"");
    assert.equal(await page.evaluate(async () => (await (await caches.open("chesifa-social-local-v1")).keys()).length),0);
    assert.equal(await page.evaluate(() => window.segnalazioniTest.length), 0);
    await page.locator("#seg-autorizzato").check();
    await page.locator("#btn-invia-segnalazione").click();
    const sent = await page.evaluate(() => window.segnalazioniTest);
    assert.equal(sent.length,1);
    assert.equal(sent[0].fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.equal(sent[0].dataInizio,date);
    assert.equal(sent[0].locandinaUrl,"");
    assert.ok(!JSON.stringify(sent).includes("prova.png"));
    assert.deepEqual(errors, []);
    console.log("OK segnalazioni social: compilazione, condivisione POST con foto, bozza locale consumata e invio esplicito.");
  } finally {
    await browser.close();
  }
})().catch(err => {console.error(err); process.exitCode = 1;});

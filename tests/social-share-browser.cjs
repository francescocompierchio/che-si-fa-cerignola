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
    await page.locator("#quick-link").fill(text);
    await page.locator("#quick-nota").evaluate(el=>el.parentElement.open=true);
    await page.locator("#quick-nota").fill("Nota senza fonte");
    assert.ok(await page.locator("#quick-invia").isDisabled());
    assert.equal(await page.evaluate(({text,date})=>CsfQuick.payload(text,"","",new Date().toISOString(),{title:"DJ Set",venue:"Sala",city:"Cerignola",date,time:"22:30"}),{text,date}),null);
    assert.equal(await page.evaluate(()=>window.segnalazioniTest.length),0);
    await page.locator("#quick-nota").fill("");
    await page.locator("#quick-link").fill(source);
    assert.equal(await page.evaluate(source=>CsfQuick.publicUrl(source),source),"https://www.instagram.com/reel/AbCd1234/");
    assert.ok(await page.locator("#quick-invia").isDisabled());
    const fillDetails=async()=>{for(const [k,v] of Object.entries({title:"DJ Set di prova",venue:"Sala di prova",city:"Cerignola",date,time:"22:30"}))await page.locator("#quick-"+k).fill(v);};
    await fillDetails();
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    let first=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(first.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(first.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.equal(first.dataInizio,date);assert.equal(first.citta,"Cerignola");assert.equal(first.luogo,"Sala di prova");
    assert.ok(!first.screenshot);
    await page.locator("#quick-foto").setInputFiles({name:"screenshot.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAQElEQVR4nGP8//8/Ay0BE01NHxYWsCBzJNwXU8XQFztj4eyhH0SjFoxaMGrBqAWjFoxaMGrBCLGAcbRtOuAWAAB5ywk7zawkfQAAAABJRU5ErkJggg==","base64")});
    await page.locator("#quick-preview").waitFor({state:"visible"});
    assert.ok(await page.locator("#quick-invia").isDisabled());
    await fillDetails();
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===2);
    const second=await page.evaluate(()=>window.segnalazioniTest[1]);
    assert.ok(second.screenshot.startsWith("data:image/jpeg;base64,"));
    assert.ok(second.screenshot.length<=240000);
    assert.equal(second.fonteUrl,"");
    assert.equal(second.dataInizio,date);assert.equal(second.citta,"Cerignola");
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
        const bytes = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAQElEQVR4nGP8//8/Ay0BE01NHxYWsCBzJNwXU8XQFztj4eyhH0SjFoxaMGrBqAWjFoxaMGrBCLGAcbRtOuAWAAB5ywk7zawkfQAAAABJRU5ErkJggg=="), c => c.charCodeAt(0));
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
    assert.equal(sent.dataInizio,date);assert.equal(sent.citta,"Cerignola");
    assert.ok(!JSON.stringify(sent).includes("prova.png"));
    // Verifica il pannello admin con una bozza privata simulata: mai approvazione istantanea.
    const adm=await browser.newPage({serviceWorkers:"block"});
    adm.on("pageerror",e=>errors.push(e.message));
    await adm.addInitScript(record=>{
      window.firebase={initializeApp(){},auth:()=>({currentUser:{getIdToken:async()=>""},onAuthStateChanged:cb=>setTimeout(()=>cb({uid:"test"}),0),signOut:async()=>{}}),database:()=>({ref:path=>({on:(event,cb)=>cb({val:()=>path==="segnalazioniDaApprovare"?{"rapida-test":record}:null,numChildren:()=>0})})})};
    },first);
    await adm.route("**/*",route=>route.request().url().startsWith("http://127.0.0.1:8765/")?route.continue():route.abort());
    await adm.goto("http://127.0.0.1:8765/admin.html");
    const card=adm.locator("#lista-segnalazioni .item-card").first();
    await card.waitFor({state:"visible"});
    assert.match(await card.textContent(),/Segnalazione rapida · da verificare/);
    assert.equal(await card.getByRole("button",{name:"Approva subito"}).count(),0);
    await card.getByRole("button",{name:"Rivedi e pubblica"}).click();
    assert.equal(await adm.locator("#ev-citta").inputValue(),"Cerignola");
    assert.equal(await adm.locator("#ev-data-inizio").inputValue(),date);
    assert.equal(await adm.locator("#ev-titolo").inputValue(),"DJ Set di prova");
    assert.equal(await adm.locator("#ev-fonte").inputValue(),first.fonteUrl);
    await adm.close();
    assert.deepEqual(errors, []);
    console.log("OK segnalazioni rapide: link solo, screenshot solo, share target con foto, bozza consumata e invio esplicito.");
  } finally {
    await browser.close();
  }
})().catch(err => {console.error(err); process.exitCode = 1;});

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
              if (path === "segnalazioniDaApprovare") {if(window.testSendError)throw Object.assign(Error("sensitive test detail"),{code:window.testSendError});window.segnalazioniTest.push(value);}
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
    await page.locator("#quick-invia").click();
    assert.match(await page.locator("#quick-esito").textContent(),/Manca la prova/);
    const date = new Date(Date.now() + 4 * 86400000).toISOString().slice(0, 10);
    const text = ["Evento: DJ Set di prova", "Locale: Sala di prova", "Comune: Cerignola", "Data: "+date, "Ore 22:30"].join("\n");
    const source = "https://www.instagram.com/reel/AbCd1234/?igsh=tracking";
    for(const invalid of ["Serata di prova a Cerignola", "https://www.instagram.com/locale/", "https://example.org/", "https://www.instagram.com/stories/locale/123456789/"]){
      await page.locator("#quick-link").fill(invalid);
      await page.locator("#quick-invia").click();
      assert.match(await page.locator("#quick-esito").textContent(),/link non è valido|Allega anche uno screenshot/);
      assert.equal(await page.evaluate(v=>CsfQuick.payload(v,"nota","","2026-11-27"),invalid),null);
    }
    await page.locator("#quick-link").fill(source);
    assert.equal(await page.evaluate(source=>CsfQuick.publicUrl(source),source),"https://www.instagram.com/reel/AbCd1234/");
    await page.evaluate(()=>window.testSendError="PERMISSION_DENIED");
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>document.querySelector("#quick-esito").textContent.includes("rifiutato"));
    assert.equal(await page.locator("#quick-link").inputValue(),source);
    assert.ok(!((await page.locator("#quick-esito").textContent()).includes("sensitive test detail")));
    assert.ok(await page.locator("#quick-wa").isVisible());
    await page.evaluate(()=>window.testSendError="");
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    let first=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(first.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(first.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.ok(!first.dataInizio&&!first.citta&&!first.luogo);
    assert.ok(!first.screenshot);
    await page.locator("#quick-foto").setInputFiles({name:"screenshot.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAQElEQVR4nGP8//8/Ay0BE01NHxYWsCBzJNwXU8XQFztj4eyhH0SjFoxaMGrBqAWjFoxaMGrBCLGAcbRtOuAWAAB5ywk7zawkfQAAAABJRU5ErkJggg==","base64")});
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
      page.evaluate(async ({source,text}) => {
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
        // PNG fotografico reale sopra il vecchio limite di 8 MiB.
        const canvas=document.createElement("canvas");canvas.width=2048;canvas.height=2048;
        const ctx=canvas.getContext("2d");const im=ctx.createImageData(2048,2048);
        let seed=123456;
        for(let i=0;i<im.data.length;i+=4){for(let j=0;j<3;j++){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;im.data[i+j]=seed&255;}im.data[i+3]=255;}
        ctx.putImageData(im,0,0);
        const blob=await new Promise(r=>canvas.toBlob(r,"image/png"));
        if(blob.size<=8*1024*1024||blob.size>32*1024*1024)throw Error("Dimensione PNG test "+blob.size);
        transfer.items.add(new File([blob], "prova.png", {type:"image/png"}));
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
    assert.ok(sent.screenshot.length<=240000);
    assert.equal(sent.descrizione,"");
    assert.ok(!sent.dataInizio&&!sent.citta);
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
    assert.equal(await adm.locator("#ev-citta").inputValue(),"");
    assert.equal(await adm.locator("#ev-data-inizio").inputValue(),"");
    assert.equal(await adm.locator("#ev-titolo").inputValue(),"");
    assert.equal(await adm.locator("#ev-fonte").inputValue(),first.fonteUrl);
    await adm.close();
    assert.deepEqual(errors, []);
    console.log("OK segnalazioni rapide: link solo, screenshot solo, share target con foto, bozza consumata e invio esplicito.");
  } finally {
    await browser.close();
  }
})().catch(err => {console.error(err); process.exitCode = 1;});

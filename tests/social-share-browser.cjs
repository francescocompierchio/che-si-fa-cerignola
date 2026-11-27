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
      window.Tesseract={createWorker:async()=>({recognize:async()=>({data:{text:window.testOCR||""}}),terminate:async()=>{}})};
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
    const text = ["Evento: DJ Set di prova", "Locale: Sala di prova", "Comune: Cerignola", "Data: "+date, "Ore 22:30","Descrizione: Serata con musica dal vivo"].join("\n");
    const source = "https://www.instagram.com/reel/AbCd1234/?igsh=tracking";
    for(const invalid of ["Serata di prova a Cerignola", "https://www.instagram.com/locale/", "https://example.org/", "https://www.instagram.com/share/reel/AbCd1234/"]){
      await page.locator("#quick-link").fill(invalid);
      await page.locator("#quick-invia").click();
      assert.match(await page.locator("#quick-esito").textContent(),/link non è valido|link di condivisione non identifica/);
      assert.equal(await page.evaluate(v=>CsfQuick.payload(v,"nota","","2026-11-27"),invalid),null);
    }
    for(const link of [source,"https://www.instagram.com/stories/locale/123456789/?igsh=tracking"]){
      await page.locator("#quick-link").fill(link);
      await page.locator("#quick-invia").click();
      await page.waitForFunction(()=>document.querySelector("#quick-esito").textContent.includes("Allega lo screenshot"));
      assert.equal(await page.evaluate(()=>window.segnalazioniTest.length),0);
    }
    await page.locator("#quick-link").fill(source);
    const photo={name:"screenshot.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAQElEQVR4nGP8//8/Ay0BE01NHxYWsCBzJNwXU8XQFztj4eyhH0SjFoxaMGrBqAWjFoxaMGrBCLGAcbRtOuAWAAB5ywk7zawkfQAAAABJRU5ErkJggg==","base64")};
    // OCR parziale: un solo campo mancante, nessun invio finché non completato.
    await page.evaluate(v=>window.testOCR=v,text.replace("Locale: Sala di prova\n",""));
    await page.locator("#quick-foto").setInputFiles(photo);
    await page.waitForFunction(()=>!document.querySelector("#quick-invia").disabled&&document.querySelector("#quick-data-luogo").offsetParent!==null);
    await page.locator("#quick-invia").click();
    assert.match(await page.locator("#quick-esito").textContent(),/Completa i dati/);
    assert.equal(await page.evaluate(()=>window.segnalazioniTest.length),0);
    await page.locator("#quick-data-luogo").fill("Sala di prova");
    await page.evaluate(()=>window.testSendError="PERMISSION_DENIED");
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>document.querySelector("#quick-esito").textContent.includes("rifiutato"));
    assert.equal(await page.locator("#quick-link").inputValue(),source);
    assert.ok(!((await page.locator("#quick-esito").textContent()).includes("sensitive test detail")));
    assert.ok(await page.locator("#quick-wa").isVisible());
    await page.evaluate(()=>window.testSendError="");
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    const first=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(first.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(first.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.equal(first.titolo,"DJ Set di prova");assert.equal(first.dataInizio,date);
    assert.equal(first.dataTesto,"Ore 22:30");assert.equal(first.citta,"Cerignola");
    assert.equal(first.luogo,"Sala di prova");assert.ok(first.screenshot.startsWith("data:image/jpeg;base64,"));
    assert.ok(first.descrizione);
    // OCR completo, screenshot senza link: un solo invio.
    await page.evaluate(v=>window.testOCR=v,text);
    await page.locator("#quick-foto").setInputFiles(photo);
    await page.waitForFunction(()=>!document.querySelector("#quick-invia").disabled&&document.querySelector("#quick-draft-summary").textContent.includes("Dati rilevati"));
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===2);
    const second=await page.evaluate(()=>window.segnalazioniTest[1]);
    assert.equal(second.fonteUrl,"");assert.equal(second.titolo,first.titolo);
    // Verifica recupero HTML strutturato + locandina con risposta pubblica simulata.
    const resolved=await page.evaluate(async({date,bytes})=>{
      const url="https://iltaccodibacco.it/puglia/eventi/123.html";
      const schema={"@type":"MusicEvent",name:"Concerto",startDate:date+"T21:00:00+01:00",location:{name:"Sala",address:{addressLocality:"Cerignola"}},description:"Musica dal vivo",image:"https://iltaccodibacco.it/img_eventi/123.png"};
      const out=await CsfQuick.resolveLink(url,async(u,opt)=>{
        if(opt.credentials!=="omit"||opt.redirect!=="error")throw Error("unsafe");
        return u===url?new Response('<script type="application/ld+json">'+JSON.stringify(schema)+'</script>',{headers:{"content-type":"text/html"}}):new Response(Uint8Array.from(atob(bytes),c=>c.charCodeAt(0)),{headers:{"content-type":"image/png"}});
      });
      return {data:out.data,type:out.file.type};
    },{date,bytes:photo.buffer.toString("base64")});
    assert.equal(resolved.data.titolo,"Concerto");assert.equal(resolved.data.dataTesto,"21:00");assert.equal(resolved.type,"image/png");
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
    await page.waitForFunction(()=>!document.querySelector("#quick-invia").disabled&&document.querySelector("#quick-preview").offsetParent!==null);
    assert.ok(await page.locator("#seg-rapida").isVisible());
    assert.ok(await page.locator("#form-segnalazione-pubblica").isHidden());
    assert.equal(new URL(page.url()).search,"");
    assert.equal(await page.evaluate(async () => (await (await caches.open("chesifa-social-local-v1")).keys()).length),0);
    assert.equal(await page.evaluate(() => window.segnalazioniTest.length),0);
    for(const [id,value] of [["titolo","DJ Set"],["luogo","Sala"],["citta","Cerignola"],["dataInizio",date],["dataTesto","22:30"],["descrizione","Serata con musica"]]){const field=page.locator("#quick-data-"+id);if(await field.isVisible())await field.fill(value);}
    await page.locator("#quick-invia").click();
    await page.waitForFunction(()=>window.segnalazioniTest.length===1);
    const sent=await page.evaluate(()=>window.segnalazioniTest[0]);
    assert.equal(sent.tipoSegnalazione,"Segnalazione rapida");
    assert.equal(sent.fonteUrl,"https://www.instagram.com/reel/AbCd1234/");
    assert.ok(sent.screenshot.startsWith("data:image/jpeg;base64,"));
    assert.ok(sent.screenshot.length<=240000);
    assert.ok(sent.descrizione&&sent.dataInizio&&sent.citta);
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
    assert.match(await card.textContent(),/Segnalazione rapida · DJ Set di prova/);
    assert.equal(await card.getByRole("button",{name:"Approva subito"}).count(),0);
    await card.getByRole("button",{name:"Verifica e approva"}).click();
    assert.equal(await adm.locator("#ev-citta").inputValue(),"Cerignola");
    assert.equal(await adm.locator("#ev-data-inizio").inputValue(),date);
    assert.equal(await adm.locator("#ev-titolo").inputValue(),first.titolo);
    assert.ok(await adm.locator("#ev-locandina-preview").isVisible());
    assert.equal(await adm.locator("#ev-fonte").inputValue(),first.fonteUrl);
    await adm.close();
    assert.deepEqual(errors, []);
    console.log("OK segnalazioni complete: OCR, dati mancanti, link non leggibile rifiutato, immagine allegata, link strutturato simulato, share target e anteprima admin.");
  } finally {
    await browser.close();
  }
})().catch(err => {console.error(err); process.exitCode = 1;});

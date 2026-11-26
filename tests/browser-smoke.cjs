const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true,serviceWorkers:"block",timezoneId:"Europe/Rome",userAgent:"Mozilla/5.0 (Linux; Android 16; Pixel 9; wv) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36"});
    const errors = []; page.on("pageerror", e => errors.push(e.message));
    await page.route("**/*", r => r.request().url().startsWith("http://127.0.0.1:8765/") ? r.continue() : r.abort());
    await page.clock.setFixedTime(new Date("2026-11-24T18:00:00+01:00"));
    await page.goto("http://127.0.0.1:8765/index.html");
    await page.locator("#events-container details").first().waitFor();
    // Community: il dock non deve coprire accesso o chiusura, anche su schermi piccoli.
    for(const [width,height] of [[320,568],[393,852],[430,740]]){
      await page.setViewportSize({width,height});
      const tab=await page.locator("#csfc-toggle").boundingBox();
      assert.ok(tab&&tab.x>=0&&tab.x+tab.width<=width-5&&tab.width>=43&&tab.height>=95,"Linguetta interamente dentro lo schermo e leggibile");
      assert.equal(await page.locator("#csfc-toggle").evaluate(el=>getComputedStyle(el).writingMode),"horizontal-tb","Testo normale ruotato, senza layout verticale nativo");
      assert.ok(tab&&tab.y>=0&&tab.y+tab.height<=height*.42,"Linguetta Community più in alto, fuori dai filtri rapidi");
      await page.locator("#csfc-toggle").click();
      const panel=page.locator("#csfc-panel");
      await panel.waitFor({state:"visible"});
      const login=panel.getByRole("button",{name:"Accedi con Google"});
      assert.equal(await panel.locator("#csfc-consent").count(),0,"Nessuna casella obbligatoria");
      assert.ok(await panel.locator("#csfc-rules-notice a").isVisible(),"Informativa accessibile");
      await login.click({trial:true});
      const bounds=await panel.evaluate(el=>{const p=el.getBoundingClientRect(),d=document.querySelector(".mobile-dock").getBoundingClientRect();return {top:p.top,bottom:p.bottom,left:p.left,right:p.right,dock:d.top,width:document.documentElement.clientWidth};});
      assert.ok(bounds.top>=0&&bounds.left>=0&&bounds.right<=bounds.width+1&&bounds.bottom<=bounds.dock,"Community sopra il dock: "+JSON.stringify(bounds));
      await panel.getByRole("button",{name:"Chiudi community"}).click();
      assert.ok(await panel.isHidden());
    }
    await page.setViewportSize({width:393,height:852});

    const acq=page.locator("#events-container details").filter({hasText:"Acquolina in Cena Spettacolo"});
    assert.equal(await acq.count(),1,"Acquolina deve essere presente");
    assert.ok(await acq.evaluate(el=>el.classList.contains("is-featured")),"Acquolina in evidenza");
    assert.ok(await acq.locator("img.event-poster").count(),"Locandina Acquolina presente");
    for(const [titolo,filename] of [["Serataccia Italiana – Carlito's","carlitos-serataccia-2026-11-25.avif"],["La Grande Spaghettata – Lion's","lions-spaghettata-2026-11-26.avif"],["Karaoke di venerdì – Lion's","lions-karaoke-2026-11-27.avif"],["Love Generation 90 – Domus Disco","domus-love-generation-2026-11-28.avif"]]){
      const el=page.locator("#events-container details").filter({hasText:titolo});
      assert.equal(await el.count(),1,titolo+" presente una sola volta");
      assert.ok(await el.evaluate(d=>d.classList.contains("is-featured")),titolo+" in evidenza");
      assert.ok(await el.locator("img.event-poster").count(),titolo+" locandina presente");
    }
    assert.ok(await acq.evaluate(el=>Array.from(el.parentElement.querySelectorAll("details")).slice(0,Array.from(el.parentElement.querySelectorAll("details")).indexOf(el)).every(x=>x.classList.contains("is-featured"))),"Acquolina nel gruppo in evidenza");
    await page.clock.setFixedTime(new Date("2026-11-25T12:27:00+01:00"));
    await page.reload();
    const serata=page.locator("#events-container details").filter({hasText:"Serataccia Italiana – Carlito's"});
    await serata.waitFor({state:"visible"});
    assert.equal(await serata.locator(".badge-today").textContent(),"OGGI");
    assert.ok(await serata.evaluate(el=>el.classList.contains("is-featured")&&el.classList.contains("is-today")));
    assert.equal(await serata.evaluate(el=>getComputedStyle(el).borderLeftColor),await page.locator("#events-container details").filter({hasText:"Acquolina in Cena Spettacolo"}).evaluate(el=>getComputedStyle(el).borderLeftColor),"Bordo dorato uniforme");
    await page.clock.setFixedTime(new Date("2026-11-24T18:00:00+01:00"));
    await page.reload();
    await page.locator("#events-container details").first().waitFor();
    assert.ok(await page.locator("#btn-apk-footer").isVisible());
    assert.ok(await page.locator("#btn-add-home").isVisible(),"WebView non nasconde installazione");
    await page.locator("#btn-add-home").click();
    assert.ok(await page.locator("#install-box").isVisible());
    assert.ok(await page.locator("#btn-apk-drawer").isVisible());
    await page.locator("#close-install-drawer").click();
    assert.ok(await page.locator("#btn-apk-alternativo").isVisible(),"APK sempre recuperabile anche da WebView");
    assert.equal(await page.locator("#btn-apk-alternativo").getAttribute("href"),"app-release.apk");
    // Simula valori pubblici senza contattare Firebase: tutti i badge devono stare sulla stessa riga.
    const conteggioOriginale = await page.locator("#event-counter").textContent();
    await page.evaluate(()=>{
      document.getElementById("event-counter").textContent="89 eventi";
      document.getElementById("online-users-count").textContent="2";
      document.getElementById("total-views-count").textContent="1381";
      for(const id of ["live-pill","views-pill"])document.getElementById(id).style.display="inline-flex";
    });
    for(const width of [320,360,393,430]){
      await page.setViewportSize({width,height:852});
      const badge=await page.locator(".stats-row > span").evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,center:r.top+r.height/2};}));
      assert.equal(badge.length,3);
      assert.ok(badge.every(r=>Math.abs(r.center-badge[0].center)<2&&r.left>=0&&r.right<=width),"Contatori a capo o fuori schermo a "+width+" px");
    }
    await page.setViewportSize({width:393,height:852});
    await page.evaluate(originale=>{document.getElementById("event-counter").textContent=originale;for(const id of ["live-pill","views-pill"])document.getElementById(id).style.display="none";},conteggioOriginale);
    for(const width of [320,360,393,430]){
      await page.setViewportSize({width,height:852});
      const layout=await page.evaluate(()=>{
        const rect=id=>{const r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,height:r.height};};
        const buttons=["quick-all","quick-weekend","quick-favorites","surprise-me"].map(rect);
        return {buttons,agenda:document.querySelector(".agenda-panel").getBoundingClientRect().height,w:document.documentElement.clientWidth};
      });
      assert.ok(layout.buttons.every(r=>Math.abs(r.top-layout.buttons[0].top)<2&&r.left>=0&&r.right<=layout.w&&r.height>=44),"Comandi rapidi fuori riga a "+width);
      assert.ok(layout.agenda<155,"Agenda non compatta a "+width+": "+layout.agenda);
    }
    await page.setViewportSize({width:393,height:852});
    assert.match(await page.locator("#author-signature").textContent(),/Francesco Compierchio/);
    assert.equal(await page.locator("#btn-author-ig").getAttribute("href"),"https://www.instagram.com/francesco_c_92/");
    assert.equal(await page.locator(".footer-links a").count(),5);
    // Una data oltre la settimana deve essere consultabile e mostrare solo eventi di quel giorno.
    await page.locator("#agenda-future-date").fill("2026-12-31");
    assert.ok(await page.locator("#events-container details").filter({hasText:"Capodanno in Piazza"}).count(),"Evento futuro già presente");
    assert.equal(await page.locator("#agenda-future-date").inputValue(),"2026-12-31");
    assert.ok(await page.locator("#agenda-selected-info").isVisible());
    await page.locator("#clear-selected-date").click();
    await page.locator("#quick-weekend").click();
    await page.locator("#agenda-new-year").click();
    assert.equal(await page.locator("#agenda-new-year").getAttribute("aria-pressed"),"true");
    assert.ok(await page.locator("#events-container details").filter({hasText:"Regiohotel Manfredi"}).count(),"Cenoni e pranzi di Capodanno");
    assert.ok(await page.locator("#events-container details").filter({hasText:"Capodanno in Piazza"}).count(),"Include feste in piazza");
    assert.ok(await page.locator("#events-container details").filter({hasText:"Capodanno al Curci"}).count(),"Include spettacoli specifici di Capodanno");
    for(const titolo of ["Cenerentola 301","Mario Schifano e gli altri","Christmas Wonderland"]){
      assert.equal(await page.locator("#events-container details").filter({hasText:titolo}).count(),0,"Esclude intervalli generici: "+titolo);
    }
    assert.ok(await page.evaluate(()=>{
      const [start,end]=dateCapodanno(),map=new Map(tuttiEventiAttivi.map(ev=>[chiaveEvento(ev),ev]));
      const shown=[...document.querySelectorAll("#events-container details")].map(el=>map.get(el.dataset.eventKey));
      return shown.length>0&&shown.every(ev=>eventoCapodanno(ev,start,end))&&Number(document.getElementById("agenda-new-year").textContent.split("·").pop().trim())===shown.length;
    }),"Conteggio coerente con gli eventi specifici");
    assert.ok(await page.evaluate(()=>{
      const [start,end]=dateCapodanno();
      return eventoCapodanno({titolo:"Veglione di San Silvestro",descrizione:"Cena con DJ set",dataInizio:start},start,end)&&eventoCapodanno({titolo:"Veglione di Capodanno",descrizione:"Concerto e brindisi",dataInizio:start,dataFine:end},start,end)&&eventoCapodanno({titolo:"Pranzo di Capodanno",dataInizio:end},start,end)&&eventoCapodanno({titolo:"NYE DJ Set",dataInizio:start},start,end)&&!eventoCapodanno({titolo:"Mostra natalizia",dataInizio:"2026-12-06",dataFine:end},start,end)&&!eventoCapodanno({titolo:"Capodanno",dataInizio:start,dataFine:"2027-01-07"},start,end);
    }),"Classificazione tematica e date precise");
    await page.locator("#clear-selected-date").click();
    assert.equal(await page.locator("#agenda-date-buttons button").count(),7);
    assert.equal(await page.locator("#sort-events").count(),0,"Ordinamento manuale eliminato");
    const ordinati=await page.evaluate(()=>{
      const map=new Map(tuttiEventiAttivi.map(ev=>[chiaveEvento(ev),ev]));
      return [...document.querySelectorAll("#events-container details")].map(el=>map.get(el.dataset.eventKey)).filter(ev=>ev&&ev.tipoContenuto!=="esperienza");
    });
    assert.ok(ordinati.every((ev,i)=>i===0||Number(!!ordinati[i-1].inEvidenza)>Number(!!ev.inEvidenza)||(!!ordinati[i-1].inEvidenza===!!ev.inEvidenza&&ordinati[i-1].dataInizio<=ev.dataInizio)),"Prima evidenza, poi cronologia");
    await page.locator("#surprise-me").click();
    assert.ok(await page.locator("#events-container details[open]").count()>0);
    await page.locator("#search-input").fill("Cosa fare nel weekend a Cerignola?");
    await page.waitForFunction(()=>Array.from(document.querySelectorAll("#events-container details")).some(el=>el.textContent.includes("Il Sabato di ADE")));
    await page.locator("#search-input").fill("Discoteche a Trani sabato sera");
    await page.waitForFunction(()=>Array.from(document.querySelectorAll("#events-container details")).some(el=>el.textContent.includes("APHELION CLUB")));
    assert.ok(await page.locator("#events-container details").filter({hasText:"APHELION CLUB"}).count());
    await page.locator("#search-input").fill("evento-inesistente-zzyyx");
    await page.locator(".empty-state").waitFor();
    await page.getByRole("button",{name:"Mostra tutte le proposte"}).click();
    assert.equal(await page.locator("#search-input").inputValue(),"");
    await page.locator("#search-input").fill("Il Sabato di ADE");
    await page.waitForFunction(()=>document.querySelectorAll("#events-container details").length===1);
    const card = page.locator("#events-container details").filter({hasText:"Il Sabato di ADE"});
    await card.first().waitFor(); assert.equal(await card.count(),1);
    await card.locator("summary").click();
    assert.ok(await card.evaluate(el => el.open));
    await page.evaluate(()=>renderEventi());
    assert.ok(await card.evaluate(el => el.open), "La scheda aperta deve sopravvivere al rendering");
    await card.locator(".favorite-toggle").click();
    await page.locator("#search-input").fill("");
    await page.locator("#quick-favorites").click();
    assert.equal(await page.locator("#events-container details").count(),1);
    await page.reload(); await page.locator("#events-container details").first().waitFor();
    await page.locator("#quick-favorites").click();
    assert.equal(await page.locator("#events-container details").count(),1);
    await page.locator("#quick-weekend").click();
    assert.ok(await page.locator("#weekend-share").isVisible());
    assert.ok(await page.locator("#events-container details").filter({hasText:"Il Sabato di ADE"}).count());
    await page.locator("#btn-segnala-evento").click();
    assert.ok(await page.locator("#modal-segnala").isVisible());
    await page.locator("#btn-chiudi-modale").click();
    assert.ok(await page.locator("#csf-consent").isHidden(), "Nessuna richiesta automatica di consenso");
    assert.equal(await page.evaluate(()=>window.CsfMetrics.allowed()),false);
    await page.locator("#csf-consent-settings").click();
    assert.ok(await page.locator("#csf-consent").isVisible());
    await page.locator("#csf-consent-no").click();
    await page.waitForFunction(() => localStorage.getItem("csf_statistiche_consent_v1")==="no");
    await page.locator("#events-container details").first().waitFor();
    assert.ok(await page.locator("#csf-consent").isHidden());
    await page.goto("http://127.0.0.1:8765/index.html?segnala=1&luogo=Locale%20Test&citta=Cerignola");
    assert.ok(await page.locator("#modal-segnala").isVisible());
    assert.equal(await page.locator("#seg-luogo").inputValue(),"Locale Test");
    assert.equal(await page.locator("#seg-citta").inputValue(),"Cerignola");
    const chrome=await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true,serviceWorkers:"block",userAgent:"Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36"});
    chrome.on("pageerror",e=>errors.push(e.message));
    await chrome.route("**/*",r=>r.request().url().startsWith("http://127.0.0.1:8765/")?r.continue():r.abort());
    await chrome.addInitScript(()=>{
      const proto=window.AudioBufferSourceNode?.prototype;
      if(!proto)return;
      const start=proto.start;
      proto.start=function(...args){
        if(this.buffer)window.__csfAudio={duration:this.buffer.duration,channels:this.buffer.numberOfChannels,loop:this.loop};
        return start.apply(this,args);
      };
    });
    await chrome.goto("http://127.0.0.1:8765/index.html");
    await chrome.locator("#events-container details").first().waitFor();
    assert.ok(await chrome.locator("#install-box").isHidden());
    assert.ok(await chrome.locator("#btn-add-home").isVisible());
    await chrome.emulateMedia({reducedMotion:"no-preference"});
    await chrome.evaluate(()=>document.addEventListener("pointerup",()=>{
      const wave=document.querySelector(".csf-liquid-wave");
      window.__waveOnTouch=wave?getComputedStyle(wave).pointerEvents:null;
    },{once:true}));
    await chrome.locator(".hero h1").tap();
    assert.equal(await chrome.evaluate(()=>window.__waveOnTouch),"none","Onda anche su testo non interattivo, senza intercettare i tocchi");
    await chrome.waitForFunction(()=>!document.querySelector(".csf-liquid-wave"));
    await chrome.waitForFunction(()=>document.getElementById("csf-music-toggle")?.dataset.musicState==="playing");
    assert.deepEqual(await chrome.evaluate(()=>window.__csfAudio),{duration:180,channels:2,loop:false},"Composizione stereo completa di tre minuti, senza loop");
    await chrome.locator("#csf-music-toggle").click();
    assert.equal(await chrome.locator("#csf-music-toggle").getAttribute("aria-pressed"),"false");
    assert.equal(await chrome.evaluate(()=>localStorage.getItem("csf_music_v1")),"off");
    await chrome.emulateMedia({reducedMotion:"reduce"});
    await chrome.locator(".hero h1").tap();
    assert.equal(await chrome.locator(".csf-liquid-wave").count(),0,"Rispetta movimento ridotto");
    await chrome.emulateMedia({reducedMotion:"no-preference"});
    await chrome.waitForFunction(()=>document.documentElement.classList.contains("csf-page-arrive"));
    assert.equal(await chrome.locator("#btn-add-home .nav-tool-copy").textContent(),"Aggiungi a Home");
    assert.equal(await chrome.locator("#btn-open-venues .nav-tool-copy").textContent(),"Instagram Locali");
    assert.equal(await chrome.locator(".nav-shortcuts small").count(),0);
    await chrome.locator("#btn-share-nav").click();
    const shareMenu=chrome.locator("#csf-share-dialog");
    await shareMenu.waitFor({state:"visible"});
    assert.match(await shareMenu.getByRole("link",{name:"WhatsApp",exact:true}).getAttribute("href"),/^https:\/\/wa\.me\//);
    assert.match(await shareMenu.getByRole("link",{name:"Telegram",exact:true}).getAttribute("href"),/^https:\/\/t\.me\/share\/url/);
    assert.match(await shareMenu.getByRole("link",{name:"Apri Messenger",exact:true}).getAttribute("href"),/^https:\/\/www\.messenger\.com\//);
    assert.ok(await shareMenu.getByRole("button",{name:"Messenger · copia messaggio",exact:true}).isVisible());
    assert.equal(await shareMenu.locator('a[href*="facebook.com/sharer"]').count(),0,"Nessun post pubblico Facebook al posto di Messenger");
    assert.ok(await shareMenu.getByRole("button",{name:"Instagram Direct · copia messaggio",exact:true}).isVisible());
    assert.match(await shareMenu.getByRole("link",{name:"Apri Direct",exact:true}).getAttribute("href"),/^https:\/\/www\.instagram\.com\/direct\/inbox\//);
    await shareMenu.getByRole("button",{name:"Chiudi"}).click();
    await chrome.locator("#btn-add-home").click();
    assert.ok(await chrome.locator("#install-guide").isVisible());
    assert.ok(await chrome.locator("#btn-apk-top").isHidden(),"Nessun secondo pulsante di installazione");
    assert.ok(await chrome.locator("#btn-apk-drawer").isVisible(),"Download APK nel pannello installazione");
    await chrome.locator("#close-install-drawer").click();
    assert.ok(await chrome.locator("#install-box").isHidden());
    for(const width of [320,360,393,430]){
      await chrome.setViewportSize({width,height:852});
      assert.ok(await chrome.locator(".top-nav-inner").evaluate(el=>el.scrollWidth<=el.clientWidth+1),"Barra strumenti fuori schermo a "+width);
      const shortcuts=await chrome.locator(".nav-shortcuts .nav-tool").evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,right:r.right,top:r.top,height:r.height,width:r.width};}));
      assert.equal(shortcuts.length,2);
      assert.ok(shortcuts.every(r=>r.x>=0&&r.right<=width&&r.height>=44&&r.width>=44),"Area tocco o larghezza insufficiente a "+width);
      assert.ok(shortcuts[1].x-shortcuts[0].right>=8,"Comandi troppo ravvicinati a "+width);
    }
    await chrome.setViewportSize({width:393,height:852});
    const searchTop=await chrome.locator("#search-input").evaluate(el=>el.getBoundingClientRect().top);
    await chrome.locator("#btn-open-venues").click();
    assert.ok(await chrome.locator("#venues-drawer").evaluate(el=>el.classList.contains("open")));
    assert.equal(await chrome.locator("#search-input").evaluate(el=>el.getBoundingClientRect().top),searchTop,"Il pannello non deve spostare la homepage");
    await chrome.locator("#btn-close-venues").click();
    assert.equal(await chrome.locator("#btn-open-venues").getAttribute("aria-expanded"),"false");
    await chrome.reload();
    await chrome.locator("#events-container details").first().waitFor();
    await chrome.locator("#events-container details").first().locator("summary").click();
    assert.equal(await chrome.locator("#csf-music-toggle").getAttribute("data-music-state"),"off","Preferenza audio conservata dopo reload e tocco");
    assert.ok(await chrome.locator("#install-box").isHidden(),"Non mostrare una seconda sezione dopo apertura evento");
    await chrome.goto("http://127.0.0.1:8765/index.html?installa=1");
    assert.ok(await chrome.locator("#install-box").isVisible());
    assert.ok(await chrome.locator("#install-guide").isVisible());
    await chrome.evaluate(()=>{const e=new Event("beforeinstallprompt");e.prompt=async()=>{window.__promptInvoked=true;};e.userChoice=Promise.resolve({outcome:"accepted"});window.dispatchEvent(e);});
    await chrome.locator("#btn-native-install").click();
    assert.ok(await chrome.evaluate(()=>window.__promptInvoked));
    await chrome.evaluate(()=>window.dispatchEvent(new Event("appinstalled")));
    assert.ok(await chrome.locator("#install-box").isHidden());
    assert.ok(await chrome.locator("#home-shortcut").isVisible(),"Controllo accessibile anche dopo appinstalled");
    await chrome.locator("#btn-add-home").click();
    assert.ok(await chrome.locator("#guide-installed").isVisible());
    await chrome.locator("#close-install-drawer").click();
    assert.ok(await chrome.locator("#btn-apk-alternativo").isVisible(),"Installazione PWA non nasconde il download APK");
    await chrome.close();
    const social=await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true,serviceWorkers:"block",userAgent:"Mozilla/5.0 (Linux; Android 16; Pixel 9; wv) AppleWebKit/537.36 Chrome/140.0.0.0 Mobile Safari/537.36 Instagram"});
    social.on("pageerror",e=>errors.push(e.message));
    await social.route("**/*",r=>r.request().url().startsWith("http://127.0.0.1:8765/")?r.continue():r.abort());
    await social.goto("http://127.0.0.1:8765/index.html?installa=1");
    assert.ok(await social.locator("#guide-social").isVisible());
    assert.ok(await social.locator("#guide-apk").isHidden());
    // Il pannello installazione è modale: chiuderlo prima di interagire col footer.
    await social.locator("#close-install-drawer").click();
    assert.ok(await social.locator("#install-box").isHidden());
    assert.ok(await social.locator("#csf-consent").isHidden());
    assert.equal(await social.evaluate(()=>window.CsfMetrics.allowed()),false);
    await social.locator("#csf-consent-settings").click();
    await social.locator("#csf-consent-yes").click();
    await social.waitForFunction(()=>localStorage.getItem("csf_statistiche_consent_v1")==="yes" && window.CsfMetrics?.allowed());
    await social.locator("#csf-consent").waitFor({state:"hidden"});
    assert.ok(await social.locator("#install-box").isHidden(),"La scelta del consenso non deve riaprire il pannello Home");
    await social.locator("#csf-consent-settings").click();
    await social.locator("#csf-consent-no").click();
    await social.waitForFunction(()=>localStorage.getItem("csf_statistiche_consent_v1")==="no" && !window.CsfMetrics?.allowed());
    await social.close();
    assert.deepEqual(errors,[]);
    console.log("OK: avvio, ricerca, scheda, preferiti persistenti, weekend, modulo, consenso.");
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exitCode=1;});

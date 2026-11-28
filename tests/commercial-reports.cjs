const assert=require("node:assert/strict");global.CsfExtras=require("../app-extras.js");require("../quick-report.js");const q=global.CsfQuick;
const s={tipoSegnalazione:"Segnalazione rapida",titolo:"DJ Set",luogo:"Caffè Roma",citta:"Cerignola",dataInizio:"2026-12-01",fonteUrl:"https://example.org/post/1?utm_source=x"};
assert.equal(q.channel(s),"editoriale");assert.equal(q.channel({...s,tipoSegnalazione:"Evento / Serata",contatto:"@locale"}),"professionale-dichiarato");
assert.equal(q.channel({...s,tipoSegnalazione:"Evento / Serata",contatto:"Segnalazione da fonte pubblica"}),"editoriale");
assert.ok(q.sameEvent(s,{...s,luogo:"CAFFE ROMA",fonteUrl:"https://example.org/post/1"}));
assert.ok(!q.sameEvent(s,{...s,citta:"Foggia"}));assert.ok(!q.sameEvent(s,{...s,dataInizio:"2026-12-02"}));
assert.ok(!q.sameEvent(s,{...s,titolo:"Concerto",fonteUrl:"https://example.org/post/2"}));
const result=q.reviewSignals(s,[{...s},{...s,dataInizio:"2026-12-02"}],[{...s,dataInizio:"2026-12-03"}]);
assert.ok(result.duplicatePending&&result.recurring&&!result.duplicatePublished);
assert.ok(q.reviewSignals(s,[],[{...s}]).duplicatePublished);
assert.ok(!q.reviewSignals(s,[{...s,citta:"Foggia"}],[]).recurring);
const fs=require("node:fs");for(const p of ["index.html","admin.html"]){const html=fs.readFileSync(p,"utf8");for(const m of html.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/gi)){if(!/application\/ld\+json/.test(m[0]))new Function(m[1]);}}
console.log("OK canali, duplicati, ricorrenze e sintassi");
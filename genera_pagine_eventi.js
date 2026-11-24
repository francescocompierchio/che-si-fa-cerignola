"use strict";
const CsfEventTools = require("./event-tools.js");
function genera(eventi, editoriali, oggi) {
 const base="https://francescocompierchio.github.io/che-si-fa-cerignola/";
 const esc=v=>String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
 const slug=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
 const safe=v=>typeof v==="string"&&/^https?:\/\/[a-z0-9.-]+(?::\d+)?(?:[/?#][^\s<>"\u0000-\u001f]*)?$/i.test(v)?v:"";
 const date=v=>/^\d{4}-\d{2}-\d{2}$/.test(v||"")&& !Number.isNaN(Date.parse(v));
 const css="*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#161b26;font:16px/1.55 system-ui,sans-serif}header{background:#004aad;color:white;padding:18px;border-bottom:4px solid #f5b800}header a{color:white;font-weight:700}main,footer{max-width:680px;margin:auto;padding:20px}article{background:white;padding:20px;border-radius:14px;border:1px solid #dde3ec}h1{line-height:1.2;font-size:1.65rem}a{color:#004aad}a.btn{display:inline-block;background:#004aad;color:white;padding:10px 14px;border-radius:9px;text-decoration:none;margin:5px 5px 5px 0}img{display:block;width:100%;max-width:400px;height:auto;margin:14px auto;border-radius:10px}li{margin:12px 0}.muted{color:#556070}strong.featured{color:#805a00}";
 const layout=(title,desc,url,body,schema="",image="",indexable=true)=>`<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><meta name="description" content="${esc(desc)}"><link rel="canonical" href="${esc(url)}"><meta name="robots" content="${indexable?"index,follow":"noindex,follow"}"><link rel="icon" href="${base}1795175413227~4.jpg" type="image/jpeg"><meta property="og:site_name" content="Che Si Fa Cerignola"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${esc(url)}"><meta property="og:type" content="website"><meta property="og:image" content="${esc(image||base+"1795175413227~3.jpg")}"><meta name="twitter:card" content="summary_large_image">${schema}<script src="${base}metrics.js" defer></script><script src="${base}event-page.js" defer></script><style>${css}.consent{padding:12px;margin-bottom:12px;background:white;border:1px solid #dde3ec;border-radius:10px}button{font:inherit;color:#004aad;background:white;border:1px solid #dde3ec;padding:8px;border-radius:8px;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #f5b800;outline-offset:2px}</style></head><body><header><a href="${base}">Che Si Fa Cerignola</a></header><main><section id="csf-consent" class="consent" hidden aria-label="Preferenze statistiche"><p>Consenti le statistiche facoltative per aiutarci a migliorare il servizio? Puoi rifiutare senza perdere funzionalità.</p><button type="button" id="csf-consent-yes">Consenti statistiche</button> <button type="button" id="csf-consent-no">Rifiuta</button> · <a href="${base}privacy.html">Privacy</a></section>${body}</main><footer><a href="${base}">Torna all'app</a> · <a href="${base}eventi/">Agenda completa</a> · <a href="${base}eventi/cerignola.html">Cerignola</a> · <a href="${base}eventi/weekend.html">Weekend</a> · <a href="${base}privacy.html">Privacy</a> · <button type="button" id="csf-consent-settings">Preferenze statistiche</button></footer></body></html>\n`;
 const jsonld=obj=>`<script type="application/ld+json">${JSON.stringify(obj).replace(/</g,"\\u003c")}</script>`;
 const breadcrumbs=(items)=>jsonld({"@context":"https://schema.org","@type":"BreadcrumbList",itemListElement:items.map(([name,item],i)=>({"@type":"ListItem",position:i+1,name,item}))});
 const crumbsAgenda=[["Che Si Fa Cerignola",base],["Agenda eventi",base+"eventi/"]];
 const files={},seen=new Set(), rows=[],alias=[];
 for(const ev of [...editoriali,...eventi]){
 if(!ev||ev.tipoContenuto==="esperienza"||!date(ev.dataInizio)||!date(ev.dataFine)||ev.dataFine<oggi||ev.dataFine<ev.dataInizio||!ev.titolo||!ev.citta||!ev.luogo||!safe(ev.fonteUrl)||String(ev.categoria||"").toLowerCase().includes("cultura"))continue;
 const id=[slug(ev.citta),ev.dataInizio,slug(ev.titolo).slice(0,115)].join("-");
 if(seen.has(id))continue;seen.add(id);
 const path=`eventi/${id}.html`,url=base+path;
 const canonical=rows.find(row=>CsfEventTools.duplicate(row.ev,ev));
 if(canonical){alias.push({path,canonical:canonical.url,title:ev.titolo});continue;}
 const description=`${ev.titolo} a ${ev.citta}: ${ev.dataTesto||ev.dataInizio}, ${ev.luogo}. ${String(ev.descrizione||"").slice(0,95)}`;
 const schema={"@context":"https://schema.org","@type":"Event",name:ev.titolo,startDate:ev.dataInizio,endDate:ev.dataFine,location:{"@type":"Place",name:ev.luogo,address:{"@type":"PostalAddress",addressLocality:ev.citta,addressCountry:"IT"}},description:ev.descrizione||description,url};
 if(safe(ev.locandinaUrl))schema.image=[safe(ev.locandinaUrl)];
 if(ev.costo==="Ingresso libero")schema.isAccessibleForFree=true;
 if(ev.inEvidenza&&ev.titolo==="Il Sabato di ADE"){schema.startDate=ev.dataInizio+"T21:00:00+01:00";delete schema.endDate;schema.location.address.streetAddress="Via Tiro a Segno km 3";}
 // Orari e indirizzi solo quando documentati. Niente prezzi, organizzatori o immagini inventati.
 const indirizzo=String(ev.indirizzoMappa||"").split(",").map(x=>x.trim()).find(x=>/^(?:via|viale|piazza|piazzale|corso|contrada|strada|largo|lungomare)\s/i.test(x));
 if(indirizzo)schema.location.address.streetAddress=indirizzo;
 const orario=String(ev.dataTesto||"").match(/(?:\bore\s*|·\s*)([01]?\d|2[0-3]):([0-5]\d)\b/i);
 if(orario&&ev.dataInizio===ev.dataFine&&!schema.startDate.includes("T")){
   // A data locale nota, senza inventare l'offset o l'orario finale.
   schema.startDate=ev.dataInizio+"T"+orario[1].padStart(2,"0")+":"+orario[2]+":00";
   delete schema.endDate;
 }
 const schemaTag=(ev.dataInizio===ev.dataFine?jsonld(schema):"")+breadcrumbs([...crumbsAgenda,[ev.titolo,url]]);
 const body=`<article id="csf-event-page" data-title="${esc(ev.titolo)}" data-city="${esc(ev.citta)}" data-date="${esc(ev.dataInizio)}" data-category="${esc(ev.categoria)}">${ev.inEvidenza?'<strong class="featured">★ IN EVIDENZA</strong>':""}<p class="muted">${esc(ev.citta)} · ${esc(ev.categoria)}</p><h1>${esc(ev.titolo)}</h1><p><strong>${esc(ev.dataTesto||ev.dataInizio)}</strong></p><p>📍 ${esc(ev.luogo)} — ${esc(ev.citta)}</p>${ev.indirizzoMappa?`<p class="muted">Indirizzo: ${esc(ev.indirizzoMappa)}</p>`:""}${safe(ev.locandinaUrl)?`<img src="${esc(safe(ev.locandinaUrl))}" alt="Locandina: ${esc(ev.titolo)}" loading="lazy">`:""}<p>${esc(ev.descrizione||"Consulta la fonte per ulteriori informazioni.")}</p>${ev.costo?`<p>Accesso: ${esc(ev.costo)}</p>`:""}<p><a class="btn" data-csf-action="csf_event_map" href="https://www.google.com/maps/search/?api=1&amp;query=${encodeURIComponent(ev.indirizzoMappa||ev.luogo+", "+ev.citta)}">Naviga</a><a class="btn" data-csf-action="csf_event_source" href="${esc(safe(ev.fonteUrl))}" rel="noopener noreferrer">Fonte dell'evento</a> <button type="button" id="csf-share-event" hidden>Condividi evento</button></p><p class="muted">Verifica con l'organizzatore eventuali variazioni di orario o programma.</p><a href="${base}">Tutti gli eventi sull'app</a></article><p><a href="${base}eventi/">Altri eventi in programma</a></p>`;
 files[path]=layout(`${ev.titolo} a ${ev.citta} | Che Si Fa Cerignola`,description,url,body,schemaTag,safe(ev.locandinaUrl));
 rows.push({path,ev,url});
 }
 for(const a of alias){files[a.path]=`<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><link rel="canonical" href="${esc(a.canonical)}"><meta http-equiv="refresh" content="0;url=${esc(a.canonical)}"><title>${esc(a.title)}</title></head><body><p>Evento unificato: <a href="${esc(a.canonical)}">apri la scheda aggiornata</a>.</p></body></html>\n`;}
 rows.sort((a,b)=>Number(b.ev.citta.toLowerCase()==="cerignola")-Number(a.ev.citta.toLowerCase()==="cerignola")||Number(!!b.ev.inEvidenza)-Number(!!a.ev.inEvidenza)||a.ev.dataInizio.localeCompare(b.ev.dataInizio));
 const fmt=v=>new Intl.DateTimeFormat("it-IT",{timeZone:"UTC",weekday:"long",day:"numeric",month:"long",year:"numeric"}).format(new Date(v+"T12:00:00Z"));
 const lista=items=>"<ul>"+items.map(x=>`<li><a href="${esc(x.url)}"><strong>${esc(x.ev.titolo)}</strong></a><br><span class="muted">${esc(x.ev.citta)} · ${esc(x.ev.dataTesto||fmt(x.ev.dataInizio))} · ${esc(x.ev.luogo)} · ${esc(x.ev.categoria||"Evento")}</span>${x.ev.descrizione?`<p>${esc(String(x.ev.descrizione).slice(0,180))}</p>`:""}</li>`).join("")+"</ul>";
 const local=rows.filter(x=>x.ev.citta.toLowerCase()==="cerignola");
 const [ven,dom]=CsfEventTools.weekend(oggi);
 const weekend=rows.filter(x=>CsfEventTools.overlaps(x.ev,oggi>ven?oggi:ven,dom));
 const nav=`<p><a href="${base}eventi/cerignola.html">Eventi a Cerignola</a> · <a href="${base}eventi/weekend.html">Cosa fare nel weekend</a></p>`;
 const localBody="<h1>Eventi a Cerignola: cosa fare in città</h1><p>Agenda locale con appuntamenti pubblicati e verificabili tramite le rispettive fonti. Gli eventi di oggi e dei prossimi giorni sono elencati con luogo e data.</p>"+(local.length?lista(local):"<p>Non risultano appuntamenti locali nel calendario pubblico. Consulta l'agenda completa o segnala un evento dall'app.</p>")+nav;
 const weekendBody="<h1>Cosa fare a Cerignola e dintorni nel weekend</h1><p><strong>"+esc(fmt(ven))+" – "+esc(fmt(dom))+"</strong></p><p>Eventi in programma tra venerdì e domenica, a partire da Cerignola. Controlla orari, prezzi e disponibilità nella scheda dell'evento.</p>"+(weekend.length?lista(weekend):"<p>Non risultano ancora eventi confermati per questo fine settimana nell'archivio pubblico. Consulta i prossimi appuntamenti nell'agenda completa.</p>")+nav;
 files["eventi/cerignola.html"]=layout("Eventi a Cerignola oggi e nei prossimi giorni | Che Si Fa Cerignola","Agenda locale di Cerignola con date, luoghi, fonti e appuntamenti in programma.",base+"eventi/cerignola.html",localBody,breadcrumbs([...crumbsAgenda,["Cerignola",base+"eventi/cerignola.html"]]),"",local.length>0);
 files["eventi/weekend.html"]=layout("Cosa fare nel weekend a Cerignola e dintorni | Che Si Fa Cerignola","Eventi del fine settimana tra Cerignola e comuni vicini, con date, luoghi e fonti.",base+"eventi/weekend.html",weekendBody,breadcrumbs([...crumbsAgenda,["Weekend",base+"eventi/weekend.html"]]),"",weekend.length>0);
 files["eventi/index.html"]=layout("Eventi a Cerignola e dintorni | Che Si Fa Cerignola","Agenda degli eventi in programma a Cerignola e nei comuni vicini.",base+"eventi/","<h1>Eventi a Cerignola e dintorni</h1><p>Serate, concerti e attività in programma. Consulta i dettagli e la fonte di ciascun evento.</p>"+nav+lista(rows),breadcrumbs(crumbsAgenda));
 const urls=[base,base+"eventi/",...(local.length?[base+"eventi/cerignola.html"]:[]),...(weekend.length?[base+"eventi/weekend.html"]:[]),...rows.map(x=>x.url)];
 files["sitemap.xml"]='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+urls.map(u=>`  <url><loc>${esc(u)}</loc></url>`).join("\n")+"\n</urlset>\n";
 return files;
}
// Lastmod indica una modifica reale del documento, non l'ora dell'esecuzione.
genera.conLastmod=function(files,precedente,leggi,oggi){
 const vecchi=new Map([...String(precedente||"").matchAll(/<url><loc>([^<]+)<\/loc><lastmod>(\d{4}-\d{2}-\d{2})<\/lastmod><\/url>/g)].map(m=>[m[1],m[2]]));
 const base="https://francescocompierchio.github.io/che-si-fa-cerignola/";
 files["sitemap.xml"]=files["sitemap.xml"].replace(/<url><loc>([^<]+)<\/loc><\/url>/g,(m,url)=>{
   if(url===base)return m;
   const path=url.slice(base.length)+(url.endsWith("/")?"index.html":"");
   if(!Object.hasOwn(files,path))return m;
   const old=leggi(path);
   const lastmod=old!==files[path]?oggi:vecchi.get(url);
   return lastmod?`<url><loc>${url}</loc><lastmod>${lastmod}</lastmod></url>`:m;
 });
 return files;
};
module.exports = genera;
if (require.main === module) {
 const fs = require("node:fs");
 const path = require("node:path");
 const html=fs.readFileSync("index.html","utf8");
 const match=html.match(/const eventiEditoriali = (\[[\s\S]*?\]);/);
 if(!match) throw Error("Archivio editoriale assente");
 const oggi=new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
 const files=genera(JSON.parse(fs.readFileSync("eventi.json","utf8")),JSON.parse(match[1]),oggi);
 const leggi=p=>{try{return fs.readFileSync(p,"utf8")}catch(_){return ""}};
 genera.conLastmod(files,leggi("sitemap.xml"),leggi,oggi);
 fs.mkdirSync("eventi",{recursive:true});
 for(const name of fs.readdirSync("eventi"))if(name.endsWith(".html")&&!Object.hasOwn(files,"eventi/"+name))fs.unlinkSync(path.join("eventi",name));
 for(const [name,content] of Object.entries(files))fs.writeFileSync(name,content);
 console.log("Pagine eventi generate:",Object.keys(files).length-2);
}

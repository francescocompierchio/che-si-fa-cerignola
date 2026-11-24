"use strict";
const CsfEventTools = require("./event-tools.js");
function genera(eventi, editoriali, oggi) {
 const base="https://francescocompierchio.github.io/che-si-fa-cerignola/";
 const esc=v=>String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
 const slug=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
 const safe=v=>typeof v==="string"&&/^https?:\/\/[a-z0-9.-]+(?::\d+)?(?:[/?#][^\s<>"\u0000-\u001f]*)?$/i.test(v)?v:"";
 const date=v=>/^\d{4}-\d{2}-\d{2}$/.test(v||"")&& !Number.isNaN(Date.parse(v));
 const css="*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#161b26;font:16px/1.55 system-ui,sans-serif}header{background:#004aad;color:white;padding:18px;border-bottom:4px solid #f5b800}header a{color:white;font-weight:700}main,footer{max-width:680px;margin:auto;padding:20px}article{background:white;padding:20px;border-radius:14px;border:1px solid #dde3ec}h1{line-height:1.2;font-size:1.65rem}a{color:#004aad}a.btn{display:inline-block;background:#004aad;color:white;padding:10px 14px;border-radius:9px;text-decoration:none;margin:5px 5px 5px 0}img{display:block;width:100%;max-width:400px;height:auto;margin:14px auto;border-radius:10px}li{margin:12px 0}.muted{color:#556070}strong.featured{color:#805a00}";
 const layout=(title,desc,url,body,schema="",image="")=>`<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><meta name="description" content="${esc(desc)}"><link rel="canonical" href="${esc(url)}"><meta name="robots" content="index,follow"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${esc(url)}"><meta property="og:type" content="website"><meta property="og:image" content="${esc(image||base+"1795175413227~3.jpg")}"><meta name="twitter:card" content="summary_large_image">${schema}<style>${css}</style></head><body><header><a href="${base}">Che Si Fa Cerignola</a></header><main>${body}</main><footer><a href="${base}">Torna all'app</a> · <a href="${base}privacy.html">Privacy</a></footer></body></html>\n`;
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
 const schemaTag=ev.dataInizio===ev.dataFine?`<script type="application/ld+json">${JSON.stringify(schema).replace(/</g,"\\u003c")}</script>`:"";
 const body=`<article>${ev.inEvidenza?'<strong class="featured">★ IN EVIDENZA</strong>':""}<p class="muted">${esc(ev.citta)} · ${esc(ev.categoria)}</p><h1>${esc(ev.titolo)}</h1><p><strong>${esc(ev.dataTesto||ev.dataInizio)}</strong></p><p>📍 ${esc(ev.luogo)} — ${esc(ev.citta)}</p>${safe(ev.locandinaUrl)?`<img src="${esc(safe(ev.locandinaUrl))}" alt="Locandina: ${esc(ev.titolo)}" loading="lazy">`:""}<p>${esc(ev.descrizione||"Consulta la fonte per ulteriori informazioni.")}</p>${ev.costo?`<p>Accesso: ${esc(ev.costo)}</p>`:""}<p><a class="btn" href="https://www.google.com/maps/search/?api=1&amp;query=${encodeURIComponent(ev.indirizzoMappa||ev.luogo+", "+ev.citta)}">Naviga</a><a class="btn" href="${esc(safe(ev.fonteUrl))}" rel="noopener noreferrer">Fonte dell'evento</a></p><p class="muted">Verifica con l'organizzatore eventuali variazioni di orario o programma.</p><a href="${base}">Tutti gli eventi sull'app</a></article><p><a href="${base}eventi/">Altri eventi in programma</a></p>`;
 files[path]=layout(`${ev.titolo} a ${ev.citta} | Che Si Fa Cerignola`,description,url,body,schemaTag,safe(ev.locandinaUrl));
 rows.push({path,ev,url});
 }
 for(const a of alias){files[a.path]=`<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><link rel="canonical" href="${esc(a.canonical)}"><meta http-equiv="refresh" content="0;url=${esc(a.canonical)}"><title>${esc(a.title)}</title></head><body><p>Evento unificato: <a href="${esc(a.canonical)}">apri la scheda aggiornata</a>.</p></body></html>\n`;}
 rows.sort((a,b)=>Number(b.ev.citta.toLowerCase()==="cerignola")-Number(a.ev.citta.toLowerCase()==="cerignola")||Number(!!b.ev.inEvidenza)-Number(!!a.ev.inEvidenza)||a.ev.dataInizio.localeCompare(b.ev.dataInizio));
 files["eventi/index.html"]=layout("Eventi a Cerignola e dintorni | Che Si Fa Cerignola","Agenda degli eventi in programma a Cerignola e nei comuni vicini.",base+"eventi/","<h1>Eventi a Cerignola e dintorni</h1><p>Serate, concerti e attività in programma. Consulta i dettagli e la fonte di ciascun evento.</p><ul>"+rows.map(x=>`<li><a href="${esc(x.url)}">${esc(x.ev.titolo)}</a><br><span class="muted">${esc(x.ev.citta)} · ${esc(x.ev.dataTesto||x.ev.dataInizio)}</span></li>`).join("")+"</ul>");
 files["sitemap.xml"]='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+[base,base+"eventi/",...rows.map(x=>x.url)].map(u=>`  <url><loc>${esc(u)}</loc></url>`).join("\n")+"\n</urlset>\n";
 return files;
}
module.exports = genera;
if (require.main === module) {
 const fs = require("node:fs");
 const path = require("node:path");
 const html=fs.readFileSync("index.html","utf8");
 const match=html.match(/const eventiEditoriali = (\[[\s\S]*?\]);/);
 if(!match) throw Error("Archivio editoriale assente");
 const oggi=new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
 const files=genera(JSON.parse(fs.readFileSync("eventi.json","utf8")),JSON.parse(match[1]),oggi);
 fs.mkdirSync("eventi",{recursive:true});
 for(const name of fs.readdirSync("eventi"))if(name.endsWith(".html")&&!Object.hasOwn(files,"eventi/"+name))fs.unlinkSync(path.join("eventi",name));
 for(const [name,content] of Object.entries(files))fs.writeFileSync(name,content);
 console.log("Pagine eventi generate:",Object.keys(files).length-2);
}

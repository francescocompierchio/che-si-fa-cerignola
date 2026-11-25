"use strict";
function strumenti(){
 const norm=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
 const slug=v=>norm(v).replace(/ /g,"-");
 const key=ev=>[ev.tipoContenuto||"evento",ev.titolo||"",ev.citta||"",ev.dataInizio||"",ev.luogo||""].join("|").toLowerCase();
 const id=ev=>[slug(ev.citta),ev.dataInizio,slug(ev.titolo).slice(0,115)].join("-");
 const validDate=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&!Number.isNaN(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 function overlaps(ev,start,end){return ev.tipoContenuto!=="esperienza"&&validDate(ev.dataInizio)&&validDate(ev.dataFine||ev.dataInizio)&&ev.dataInizio<=end&&(ev.dataFine||ev.dataInizio)>=start;}
 function weekend(oggi){const d=new Date(oggi+"T12:00:00Z"),day=d.getUTCDay(),shift=day===6?-1:day===0?-2:(5-day+7)%7;d.setUTCDate(d.getUTCDate()+shift);const start=d.toISOString().slice(0,10);d.setUTCDate(d.getUTCDate()+2);return [start,d.toISOString().slice(0,10)];}
 function duplicate(a,b){
 if(!a||!b||a.tipoContenuto==="esperienza"||b.tipoContenuto==="esperienza"||!norm(a.citta)||norm(a.citta)!==norm(b.citta)||!validDate(a.dataInizio)||a.dataInizio!==b.dataInizio||(a.dataFine||a.dataInizio)!==(b.dataFine||b.dataInizio))return false;
 const ta=norm(a.titolo),tb=norm(b.titolo);
 const la=norm(a.luogo),lb=norm(b.luogo);
 const stop=new Set(["teatro","comunale","sala","piazza","palazzo","centro","parco","chiesa","auditorium","cinema","ristorante","locale","cerignola","foggia","barletta","andria","trani","manfredonia"]);
 const sameVenue=la&&lb&&(la===lb||la.split(" ").some(x=>x.length>=5&&!stop.has(x)&&lb.split(" ").includes(x)));
 if(!sameVenue)return false;
 if(ta===tb&&ta.length>=4)return true;
 const shorter=ta.length<=tb.length?ta:tb,longer=ta.length<=tb.length?tb:ta;
 return shorter.length>=9&&(" "+longer+" ").includes(" "+shorter+" ");
 }
 function dedup(list){const out=[];for(const ev of list)if(ev&&!out.some(x=>duplicate(x,ev)))out.push(ev);return out;}
 function quality(ev){return Number(!!ev.locandinaUrl)*2+Number(!!ev.luogo)+Number(String(ev.descrizione||"").length>=60)+Number(!!ev.costo&& !/non indicato|da definire/i.test(ev.costo));}
 function evening(ev){if(ev.tipoContenuto==="esperienza")return false;const text=norm(ev.categoria);return /locali|serat/.test(text)||/\b(?:ore|start|inizio|dalle|h)\s*(?:1[89]|2[0-3])(?=[:.\s]|$)/i.test([ev.dataTesto,ev.descrizione].join(" "));}
 function shareUrl(ev,available,base){const candidate=base+"eventi/"+id(ev)+".html";return available.has(candidate)?candidate:base+"#evento="+encodeURIComponent(key(ev));}
 // Riepilogo aggiornato, senza esperienze non datate, eventi scaduti o doppioni.
 function weekendDigest(eventi,oggi){
   if(!validDate(oggi))return "";
   const [start,end]=weekend(oggi),from=oggi>start?oggi:start;
   const fmt=v=>new Intl.DateTimeFormat("it-IT",{timeZone:"UTC",weekday:"short",day:"numeric",month:"short"}).format(new Date(v+"T12:00:00Z"));
   const rows=dedup(eventi.filter(ev=>ev&&overlaps(ev,from,end)&&ev.titolo&&ev.citta&&ev.luogo)).sort((a,b)=>Number(norm(b.citta)==="cerignola")-Number(norm(a.citta)==="cerignola")||Number(evening(b))-Number(evening(a))||a.dataInizio.localeCompare(b.dataInizio)||String(a.titolo).localeCompare(String(b.titolo)));
   if(!rows.length)return "";
   // Limita a due appuntamenti per comune nel primo giro, poi completa fino a sei.
   const chosen=[],counts=new Map();
   for(const ev of rows){const c=norm(ev.citta);if((counts.get(c)||0)>=2)continue;chosen.push(ev);counts.set(c,(counts.get(c)||0)+1);if(chosen.length===6)break;}
   for(const ev of rows){if(chosen.length===6)break;if(!chosen.includes(ev))chosen.push(ev);}
   const lines=chosen.map(ev=>"• "+String(ev.titolo).replace(/\s+/g," ").slice(0,95)+" — "+fmt(ev.dataInizio)+ (ev.dataFine&&ev.dataFine!==ev.dataInizio?"–"+fmt(ev.dataFine):"")+" · "+ev.citta+" · "+String(ev.luogo).replace(/\s+/g," ").slice(0,70));
   return "CHE SI FA CERIGNOLA | Weekend "+fmt(start)+" – "+fmt(end)+"\n\n"+lines.join("\n")+(rows.length>chosen.length?"\n… e altri "+(rows.length-chosen.length)+" appuntamenti":"")+"\n\nConsulta il programma aggiornato, orari e fonti. Aggiungi l’app gratis al telefono.";
 }
 function discoteca(ev){
   if(ev.tipoContenuto==="esperienza")return false;
   const t=norm([ev.titolo,ev.luogo,ev.descrizione].join(" "));
   return /locali|serat/.test(norm(ev.categoria))&&/\b(?:discoteca|discoteche|club|dj|deejay|techno|house music|clubbing|dancefloor|dance floor|opening party|atrio22|aphelion|vyon)\b/.test(t);
 }
 function vitaNotturna(ev){
   if(ev.tipoContenuto==="esperienza")return false;
   const t=norm([ev.titolo,ev.luogo,ev.descrizione].join(" ")),cat=norm(ev.categoria);
   return /locali|serat/.test(cat)||(/musica|concert|sagre|food|attivita/.test(cat)&&/\b(?:dj|karaoke|aperitivo musicale|cena spettacolo|live music|musica dal vivo|disco|discoteca|club night)\b/.test(t));
 }
 // IN CORSO solo entro una fascia oraria esplicita, non da un semplice orario di inizio.
 function statoTemporale(ev,now=new Date()){
   const parti=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(now).map(p=>[p.type,p.value]));
   const oggi=parti.year+"-"+parti.month+"-"+parti.day;
   if(!overlaps(ev,oggi,oggi))return "";
   if(ev.dataInizio!==(ev.dataFine||ev.dataInizio))return "OGGI";
   const t=String(ev.dataTesto||"");
   const m=t.match(/\b(?:ore\s+|dalle\s+)([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:[–—-]|\balle\b)\s*(?:ore\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)\b/i);
   if(!m)return "OGGI";
   const inizio=Number(m[1])*60+Number(m[2]),fine=Number(m[3])*60+Number(m[4]),minuto=Number(parti.hour)*60+Number(parti.minute);
   return inizio<fine&&minuto>=inizio&&minuto<fine?"IN CORSO":"OGGI";
 }
 function prioritaScoperta(ev,oggi,fascia){
   if(ev.tipoContenuto==="esperienza")return 99;
   const d=new Date(oggi+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+6);
   const imminente=overlaps(ev,oggi,d.toISOString().slice(0,10));
   if(!imminente)return 6;
   if(fascia===0&&vitaNotturna(ev))return 0;
   if(fascia===0)return 1;
   if(fascia<=1&&vitaNotturna(ev))return 2;
   if(vitaNotturna(ev))return 3;
   if(fascia<=1)return 4;
   return 5;
 }
 return {norm,slug,key,id,overlaps,weekend,duplicate,dedup,quality,evening,shareUrl,weekendDigest,discoteca,vitaNotturna,statoTemporale,prioritaScoperta};
}
const CsfEventTools = strumenti();
if (typeof module !== "undefined" && module.exports) module.exports=CsfEventTools;

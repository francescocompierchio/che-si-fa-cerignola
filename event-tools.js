"use strict";
function strumenti(){
 const norm=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
 const slug=v=>norm(v).replace(/ /g,"-");
 const key=ev=>[ev.tipoContenuto||"evento",ev.titolo||"",ev.citta||"",ev.dataInizio||"",ev.luogo||""].join("|").toLowerCase();
 const id=ev=>[slug(ev.citta),ev.dataInizio,slug(ev.titolo).slice(0,115)].join("-");
 const validDate=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v);
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
 return {norm,slug,key,id,overlaps,weekend,duplicate,dedup,quality,evening,shareUrl};
}
const CsfEventTools = strumenti();
if (typeof module !== "undefined" && module.exports) module.exports=CsfEventTools;

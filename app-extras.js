"use strict";
function util(){
 const months=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 function parsePoster(text){
 const raw=String(text||"").slice(0,10000),normalized=raw.replace(/\s+/g," ");
 let date="",time="";
 const m=normalized.match(/\b(\d{1,2})[\/.-](\d{1,2})[\/.-](20\d{2})\b/)||normalized.match(new RegExp("\\b(\\d{1,2})\\s+("+months.join("|")+")\\s+(20\\d{2})\\b","i"));
 if(m){const month=/^\d+$/.test(m[2])?Number(m[2]):months.indexOf(m[2].toLowerCase())+1;const d=new Date(Date.UTC(Number(m[3]),month-1,Number(m[1])));if(d.getUTCFullYear()===Number(m[3])&&d.getUTCMonth()===month-1&&d.getUTCDate()===Number(m[1]))date=d.toISOString().slice(0,10);}
 const clock=normalized.match(/\b(?:ore|start(?:\s+ore)?|inizio(?:\s+ore)?|dalle|h)\s*([01]?\d|2[0-3])(?:[:.]([0-5]\d))?(?=\s|$)/i);
 if(clock)time="Ore "+clock[1].padStart(2,"0")+":"+(clock[2]||"00");
 return {date,time,text:raw.trim()};
 }
 function fridayCalendar(today,stamp){
 const d=new Date(today+"T12:00:00Z");
 if(!/^\d{4}-\d{2}-\d{2}$/.test(today)||!Number.isFinite(d.getTime()))throw Error("Data non valida");
 d.setUTCDate(d.getUTCDate()+((5-d.getUTCDay()+7)%7||7));const date=d.toISOString().slice(0,10).replace(/-/g,"");
 return ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Che Si Fa Cerignola//IT","CALSCALE:GREGORIAN","BEGIN:VEVENT","UID:weekend-v1@chesifacerignola","DTSTAMP:"+stamp,"DTSTART:"+date+"T180000","DTEND:"+date+"T181000","RRULE:FREQ=WEEKLY;BYDAY=FR","SUMMARY:Scopri gli eventi del weekend","DESCRIPTION:Apri Che Si Fa Cerignola per scoprire cosa fare.","URL:https://francescocompierchio.github.io/che-si-fa-cerignola/","BEGIN:VALARM","TRIGGER:PT0M","ACTION:DISPLAY","DESCRIPTION:Scopri gli eventi del weekend","END:VALARM","END:VEVENT","END:VCALENDAR"].join("\r\n")+"\r\n";
 }
 function propostaPonderata(candidati, interessi, random=Math.random){
   if(!candidati.length)return null;
   const pesi=candidati.map(x=>1+(x.locale?3:0)+(x.imminente?3:0)+(interessi.has(x.categoria)?3:0));
   let r=Math.max(0,Math.min(0.999999,random()))*pesi.reduce((a,b)=>a+b,0);
   for(let i=0;i<pesi.length;i++){r-=pesi[i];if(r<0)return candidati[i];}
   return candidati[candidati.length-1];
 }
 function datiSegnalazione(params){
   const clean=(k,n)=>String(params.get(k)||"").replace(/[\x00-\x1f\x7f]/g," ").trim().slice(0,n);
   if(params.get("segnala")!=="1")return null;
   return {luogo:clean("luogo",100),citta:clean("citta",60)};
 }
 return {parsePoster,fridayCalendar,propostaPonderata,datiSegnalazione};
}
const CsfExtras=util();
if(typeof module!=="undefined"&&module.exports)module.exports=CsfExtras;

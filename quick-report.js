"use strict";
(function(root){
 const MAX_DATA=240000, MAX_FILE=32*1024*1024, TYPES=["image/jpeg","image/png","image/webp"];
 function publicUrl(value){
  const v=String(value||"").trim();
  const parser=typeof CsfExtras!=="undefined"?CsfExtras:root.CsfExtras;
  const social=parser?.socialUrl?.(v);
  if(social)return social;
  try{
   const u=new URL(v);
   if(u.protocol!=="https:"||u.username||u.password||u.port||u.href.length>1800||!/^[a-z0-9.-]+\.[a-z]{2,63}$/i.test(u.hostname)||/\.(?:local|internal|localhost)$/i.test(u.hostname))return "";
   if(/^(?:www\.|m\.)?instagram\.com$/i.test(u.hostname)&&/^\/share\/(?:(?:reel|p)\/)?[\w-]{3,80}\/?$/.test(u.pathname))return "https://www.instagram.com"+u.pathname;
   if(/(?:^|\.)(?:instagram\.com|facebook\.com|fb\.watch|t\.me)$/i.test(u.hostname))return "";
   if(u.pathname==="/"||!u.pathname.replace(/\//g,""))return "";
   u.hash="";return u.href;
  }catch(_){return "";}
 }
 function linkFromText(v){
  return (String(v||"").match(/https:\/\/[^\s<>"']+/gi)||[]).map(x=>publicUrl(x.replace(/[.,!?)\]}]+$/g,""))).find(Boolean)||"";
 }
 function requiresScreenshot(source){
  try{const u=new URL(source),host=u.hostname.replace(/^(?:www\.|m\.|web\.)/,"");
    return (host==="instagram.com"&&/^\/share\//i.test(u.pathname))||(host==="facebook.com"&&/^\/(?:stories|share)\//i.test(u.pathname))||host==="fb.watch";
  }catch(_){return false;}
 }
 function isDirectStory(source){
  try{const u=new URL(source);return u.hostname==="www.instagram.com"&&/^\/stories\/[\w.]{1,30}\/\d{5,24}\/?$/.test(u.pathname);}catch(_){return false;}
 }
 function safeImage(v){return typeof v==="string"&&v.length<=MAX_DATA&&/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(v);}
 const fields=[["titolo","Nome dell’evento",150],["luogo","Locale o sede",200],["citta","Comune",80],["dataInizio","Data",10],["dataTesto","Orario",40],["descrizione","Descrizione",1000]];
 function clean(v,n){return typeof v==="string"?v.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g,"").trim().slice(0,n):"";}
 function draft(text,today,cities){
  const p=root.CsfExtras.parsePoster(text), raw=p.text;
  const normalize=s=>s.toLocaleLowerCase("it").normalize("NFD").replace(/[\u0300-\u036f]/g,"");
  const lines=raw.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  const cityMatches=cities.filter(c=>new RegExp("(?:^|[^a-z])"+normalize(c).replace(/[.*+?^\${}()|[\]\\]/g,"\\ function payload(input,note,image,stamp){")+"(?:$|[^a-z])").test(normalize(raw)));
  const city= p.city&&cities.find(c=>normalize(c)===normalize(p.city))|| (cityMatches.length===1?cityMatches[0]:"");
  // Only propose title/venue on explicit labels; no guessed venue from an Instagram handle.
  const title=p.title||"", venue=p.venue||"";
  const time=p.time.replace(/^Ore /,"");
  const description=lines.filter(x=>!/^(?:evento|titolo|nome dell.evento|locale|luogo|sede|comune|citt[àa]|data|ore|orario)\s*:/i.test(x)).join("\n");
  return {titolo:clean(title,150),luogo:clean(venue,200),citta:city||"",dataInizio:p.date>=today?p.date:"",dataTesto:time,descrizione:clean(description,1000),costo:clean(p.price,100)};
 }
 function missing(d,today,validCity=()=>true){
  const out=[];
  for(const [k,label,max] of fields){
   const v=clean(d?.[k],max);
   let ok=!!v;
   if(k==="dataInizio"){const date=new Date(v+"T12:00:00Z");ok=/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===v&&v>=today;}
   if(k==="dataTesto")ok=/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v);
   if(k==="citta")ok=!!v&&validCity(v);
   if(!ok)out.push(k);
  }
  return out;
 }
 // Only explicitly supported public providers. No cookies, proxy, redirect or login.
 const PUBLIC_HOSTS=new Set(["iltaccodibacco.it","www.iltaccodibacco.it","cerignolaviva.it","www.cerignolaviva.it","canosaviva.it","www.canosaviva.it","barlettaviva.it","www.barlettaviva.it","traniviva.it","www.traniviva.it","andriaviva.it","www.andriaviva.it","bisceglieviva.it","www.bisceglieviva.it","www.foggiatoday.it","foggiatoday.it"]);
 function trustedUrl(value,base){
  try{const u=new URL(value,base);return u.protocol==="https:"&&!u.username&&!u.password&&!u.port&&PUBLIC_HOSTS.has(u.hostname)?u:"";}catch(_){return "";}
 }
 async function boundedRead(url,kind,fetcher,signal){
  const r=await fetcher(url.href,{mode:"cors",credentials:"omit",redirect:"error",referrerPolicy:"no-referrer",signal});
  if(!r.ok)throw Error(r.status===404||r.status===410?"link-scaduto":"link-non-accessibile");
  const mime=(r.headers.get("content-type")||"").split(";")[0].trim().toLowerCase();
  if(kind==="html"?!["text/html","application/xhtml+xml"].includes(mime):!TYPES.includes(mime))throw Error("link-no-image");
  const limit=kind==="html"?1500000:MAX_FILE;
  if(Number(r.headers.get("content-length"))>limit||!r.body)throw Error("link-too-large");
  const reader=r.body.getReader(), chunks=[];let total=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>limit)throw Error("link-too-large");chunks.push(value);}}
  finally{try{await reader.cancel();}catch(_){}}
  const blob=new Blob(chunks,{type:mime});
  return kind==="html"?blob.text():new File([blob],"locandina",{type:mime});
 }
 function structuredEvent(html){
  const records=[];
  const visit=(x,depth=0)=>{if(!x||depth>5||records.length>4)return;if(Array.isArray(x)){x.forEach(v=>visit(v,depth+1));return;}if(typeof x!=="object")return;
   const types=Array.isArray(x["@type"])?x["@type"]:[x["@type"]];
   if(types.some(t=>typeof t==="string"&&/^(?:https?:\/\/schema\.org\/)?(?:Event|MusicEvent|FoodEvent|Festival|DanceEvent|TheaterEvent|ChildrensEvent)$/.test(t)))records.push(x);
   visit(x["@graph"],depth+1);
  };
  for(const m of html.matchAll(/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi)){try{visit(JSON.parse(m[1]));}catch(_){}}
  return records.length===1?records[0]:null;
 }
 async function resolveLink(value,fetcher=root.fetch.bind(root)){
  const source=publicUrl(value);
  if(!source)throw Error("link-invalido");
  if(isDirectStory(source)||root.CsfExtras.socialUrl(source)||requiresScreenshot(source))throw Error("link-social");
  const u=trustedUrl(source);
  if(!u)throw Error("link-not-supported");
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  try{
   if(/\.(?:jpe?g|png|webp)$/i.test(u.pathname))return {file:await boundedRead(u,"image",fetcher,controller.signal),data:null};
   const html=await boundedRead(u,"html",fetcher,controller.signal),ev=structuredEvent(html);
   if(!ev)throw Error("link-no-event");
   const image=Array.isArray(ev.image)?ev.image[0]:ev.image, imageUrl=trustedUrl(typeof image==="string"?image:image?.url||image?.contentUrl,u);
   if(!imageUrl||imageUrl.hostname!==u.hostname)throw Error("link-no-image");
   const date=clean(ev.startDate,60),match=/^(\d{4}-\d{2}-\d{2})T((?:[01]\d|2[0-3]):[0-5]\d)/.exec(date);
   // Do not assume a time zone when it differs from the event's stated local time.
   const loc=Array.isArray(ev.location)?null:ev.location, address=loc?.address;
   return {file:await boundedRead(imageUrl,"image",fetcher,controller.signal),data:{titolo:clean(ev.name,150),luogo:clean(loc?.name,200),citta:clean(address?.addressLocality,80),dataInizio:match?.[1]||(/^\d{4}-\d{2}-\d{2}$/.test(date)?date:""),dataTesto:match?.[2]||"",descrizione:clean(typeof ev.description==="string"?ev.description.replace(/<[^>]*>/g," "):"",1000)}};
  }finally{clearTimeout(timer);}
 }
 function linkError(err){return ({
  "link-social":"Instagram, Facebook o Telegram non consentono a questa app di leggere direttamente il contenuto del link. Allega lo screenshot: lo leggeremo automaticamente.",
  "link-not-supported":"La fonte non è ancora supportata per il recupero automatico. Allega uno screenshot.",
  "link-scaduto":"L’annuncio non è più disponibile. Allega uno screenshot se lo possiedi.",
  "link-no-event":"Il sito non restituisce un singolo evento riconoscibile. Allega la locandina o uno screenshot.",
  "link-no-image":"Il sito non restituisce una locandina accessibile. Allega uno screenshot.",
  "link-too-large":"Il contenuto supera i limiti di lettura. Allega uno screenshot."
 })[err?.message]||"Non è stato possibile leggere il sito (connessione, accesso o protezione del sito). Allega uno screenshot: i dati già inseriti restano qui.";}
 function payload(input,note,image,stamp,data,today,validCity){

  const n=String(note||"").trim().slice(0,500);
  const source=publicUrl(input);
  if(!safeImage(image)||!data||missing(data,today,validCity).length)return null;
  const out={tipoSegnalazione:"Segnalazione rapida",fonteUrl:source,notaRapida:n,inviatoIl:stamp,screenshot:image};
  for(const [k,,max] of fields)out[k]=clean(data[k],max);
  out.dataFine=out.dataInizio;out.dataTesto="Ore "+out.dataTesto;out.costo=clean(data.costo,100);
  return out;
 }
 async function compress(file){
  if(!file||file.size<=0)throw Error("empty-image");
  if(file.size>MAX_FILE)throw Error("image-size");
  if(!TYPES.includes(file.type))throw Error("image-format");
  const url=URL.createObjectURL(file);
  let img;
  try{
   img=await new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error("image-decode"));i.src=url;});
   const w=img.naturalWidth,h=img.naturalHeight;
   if(!w||!h||w*h>64000000)throw Error("pixels");
   const canvas=document.createElement("canvas");
   for(const max of [2000,1600,1300,1000,800]){
    const scale=Math.min(1,max/Math.max(w,h));canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
    const ctx=canvas.getContext("2d");ctx.fillStyle="#fff";ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
    for(const q of [.86,.73,.60,.48]){const data=canvas.toDataURL("image/jpeg",q);if(safeImage(data))return data;}
   }
   throw Error("dimensione");
  }finally{URL.revokeObjectURL(url);}
 }
 function imageError(err){
  return ({
   "empty-image":"Il file è vuoto. Seleziona un altro screenshot o la locandina originale.",
   "image-size":"La foto supera 32 MB. Prova un altro screenshot o incolla il link diretto all’annuncio.",
   "image-format":"Formato non supportato. Usa uno screenshot JPG, PNG o WebP oppure il link diretto.",
   "image-decode":"L’immagine non è leggibile dal dispositivo. Seleziona nuovamente l’originale o usa un altro screenshot.",
   "pixels":"La risoluzione supera il limite di sicurezza (64 megapixel) oppure l’immagine è priva di dimensioni valide. Usa uno screenshot normale o un link diretto.",
   "dimensione":"Non è stato possibile comprimere la foto entro il limite di invio. Prova un’altra immagine o usa il link diretto."
  })[err?.message]||"Il telefono non è riuscito a preparare la foto. Riprova dopo aver chiuso altre app o usa il link diretto.";
 }
 function sendError(err,online=true){
  if(!online)return "Connessione Internet assente. Riattiva Wi-Fi o dati mobili e riprova: i dati inseriti sono ancora qui.";
  const code=String(err?.code||"").toLowerCase().replace(/^database\//,"").replace(/_/g,"-");
  if(["permission-denied","unauthorized","auth/permission-denied"].includes(code))return "Il servizio ha rifiutato l’invio (autorizzazione o regole di accettazione). Se i dati sono corretti, usa WhatsApp oppure riprova più tardi.";
  if(["network-error","disconnected","unavailable","network-request-failed"].includes(code))return "Connessione al servizio interrotta o non disponibile. Controlla Internet e riprova; i dati restano nel modulo.";
  if(["quota-exceeded","resource-exhausted","limit-exceeded"].includes(code))return "Limite del servizio raggiunto. Riprova più tardi oppure usa WhatsApp.";
  if(["invalid-argument","invalid-data","validation-failed"].includes(code))return "Il servizio segnala dati non validi. Controlla i campi e il formato della foto o del link; in alternativa usa WhatsApp.";
  return "Il servizio non ha confermato l’invio e non ha fornito un motivo preciso. I dati sono ancora qui: riprova oppure usa WhatsApp.";
 }
 function evidenceError(input,image){
  if(safeImage(image))return "";
  const value=String(input||"").trim(),source=publicUrl(value);
  if(!value)return "Manca la prova dell’evento. Scegli uno screenshot o incolla il link diretto all’annuncio.";
  if(!source)return "Il link non è valido o non è un annuncio diretto. Copia il link HTTPS del singolo post oppure allega uno screenshot.";
  if(requiresScreenshot(source))return "Il link di condivisione non identifica direttamente l’annuncio. Copia il link diretto oppure allega uno screenshot.";
  return "";
 }
 root.CsfQuick={publicUrl,linkFromText,safeImage,payload,compress,requiresScreenshot,isDirectStory,imageError,sendError,evidenceError,draft,missing,fields,resolveLink,linkError,MAX_DATA,MAX_FILE};
})(typeof window!=="undefined"?window:globalThis);

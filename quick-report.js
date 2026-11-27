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
    return (host==="instagram.com"&&/^\/(?:stories|share)\//i.test(u.pathname))||(host==="facebook.com"&&/^\/(?:stories|share)\//i.test(u.pathname))||host==="fb.watch";
  }catch(_){return false;}
 }
 function safeImage(v){return typeof v==="string"&&v.length<=MAX_DATA&&/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(v);}
 function payload(input,note,image,stamp){
  const n=String(note||"").trim().slice(0,500);
  const source=publicUrl(input);
  // Stories can expire or require authentication. Preserve the visual evidence.
  if(!safeImage(image)&&(!source||requiresScreenshot(source)))return null;
  const out={tipoSegnalazione:"Segnalazione rapida",titolo:"",fonteUrl:source,descrizione:"",notaRapida:n,inviatoIl:stamp};
  if(safeImage(image))out.screenshot=image;
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
  if(requiresScreenshot(source))return "Il link della Storia o di condivisione potrebbe scadere o richiedere accesso. Allega anche uno screenshot.";
  return "";
 }
 root.CsfQuick={publicUrl,linkFromText,safeImage,payload,compress,requiresScreenshot,imageError,sendError,evidenceError,MAX_DATA,MAX_FILE};
})(typeof window!=="undefined"?window:globalThis);

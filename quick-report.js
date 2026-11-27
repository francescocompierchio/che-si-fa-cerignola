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
  if(!file||!TYPES.includes(file.type)||file.size<=0||file.size>MAX_FILE)throw Error("file");
  const url=URL.createObjectURL(file);
  let img;
  try{
   img=await new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=url;});
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
 root.CsfQuick={publicUrl,linkFromText,safeImage,payload,compress,requiresScreenshot,MAX_DATA,MAX_FILE};
})(typeof window!=="undefined"?window:globalThis);

"use strict";
(function(){
 if(typeof HTMLDialogElement==="undefined"||typeof HTMLDialogElement.prototype.showModal!=="function")return;
 const $=id=>document.getElementById(id), history=[], dialogs={}, maxResults=12;
 let active=null, gesture=null, trigger=null, generation=0, previousFocus=null;
 const events=()=>tuttiEventiAttivi.filter(e=>e.tipoContenuto!=="esperienza"&&e.dataFine>=oggi);
 const key=ev=>chiaveEvento(ev);
 const mk=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
 const menu={
 left:[["city","⌖ Eventi per comune"],["popular","↗ Più aperti"],["tonight","☾ Dove andare stasera"],["next","▦ Prossimi 7 giorni"],["places","⌖ Luoghi e indicazioni"],["surprise","🎲 Sorprendimi"]],
 right:[["recommend","✦ Consigliati per te"],["news","◉ Novità dall'ultimo controllo"],["recent","◷ Visti di recente"],["saved","☆ La mia agenda"],["prefs","⚙ Le mie preferenze"],["report","＋ Segnala un evento"]]
 };
 function busy(){return !!document.querySelector("dialog[open],.modal-backdrop.open,.venues-drawer.open")||!!$("csfc-panel")?.getClientRects().length&&getComputedStyle($("csfc-panel")).visibility!=="hidden"&&!$("csfc-panel").hidden;}
 function reset(){queryRicerca="";$("search-input").value="";impostaModalitaRapida("ALL");}
 function scrollEvents(){ $("events-container").scrollIntoView({block:"start"}); }
 function release(d){
  if(active!==d)return;
  generation++;active=null;gesture=null;
  document.documentElement.classList.remove("csf-side-open");
  const focus=previousFocus;previousFocus=null;
  focus?.focus?.({preventScroll:true});
 }
 function close(){if(active){const d=active;d.close();release(d);}}
 function showEvent(ev){close();reset();const card=[...$("events-container").querySelectorAll("details[data-event-key]")].find(n=>n.dataset.eventKey===key(ev));if(card){card.open=true;card.scrollIntoView({block:"center"});}else mostraToast("Evento non più disponibile");}
 function list(host,items,note,places=false){
  host.replaceChildren(mk("p",note));
  if(!items.length){host.append(mk("p","Nessun evento disponibile per questa selezione."));return;}
  for(const ev of items.slice(0,maxResults)){
   const b=mk("button","");b.type="button";b.append(mk("strong",ev.titolo),mk("small",[ev.dataTesto,ev.luogo,ev.citta].filter(Boolean).join(" · ")));
   b.addEventListener("click",()=>places?(close(),apriNavigazioneMappa(ev.indirizzoMappa||ev.luogo+", "+ev.citta)):showEvent(ev));host.append(b);
  }
 }
 function storageGet(k){try{return JSON.parse(localStorage.getItem(k)||"null");}catch(_){return null;}}
 function storageSet(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true;}catch(_){return false;}}
 const prefKey="csf_side_categories_v1",newsKey="csf_side_last_check_v1";
 function prefs(){const v=storageGet(prefKey);return Array.isArray(v)?v.filter(x=>typeof x==="string"):[];}
 function categories(){return [...new Set(events().map(e=>e.categoria).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"it"));}
 function chooser(host,cb){const s=mk("select");s.setAttribute("aria-label","Scegli comune");const cities=[...new Set(events().map(e=>e.citta))].sort((a,b)=>a.localeCompare(b,"it"));for(const c of cities){const o=mk("option",c);o.value=c;s.append(o);}if(cities.includes("Cerignola"))s.value="Cerignola";host.append(s);s.addEventListener("change",()=>cb(s.value));cb(s.value);}
 async function run(action,host){
  const seq=++generation,all=events();host.replaceChildren();
  if(action==="tonight"||action==="next"){close();reset();impostaFiltroSmart(action==="tonight"?"TONIGHT":"NEXT7");scrollEvents();return;}
  if(action==="surprise"){close();reset();$("surprise-me").click();return;}
  if(action==="saved"){close();reset();$("dock-saved").click();return;}
  if(action==="report"){close();$("btn-segnala-evento").click();return;}
  if(action==="city"||action==="places"){
   host.append(mk("p",action==="city"?"Scegli il comune, senza condividere la tua posizione.":"Scegli un comune e apri il navigatore per raggiungere la sede."));
   const results=mk("div","","csf-side-results");
   chooser(host,c=>list(results,all.filter(e=>e.citta===c),action==="city"?"Eventi in programma":"Indicazioni per gli eventi",action==="places"));host.append(results);return;
  }
  if(action==="recommend"){
   const preferred=new Set([...prefs(),...all.filter(e=>preferiti.has(key(e))).map(e=>e.categoria)]);
   const matching=all.filter(e=>preferred.has(e.categoria));
   list(host,matching.length?matching:all.filter(e=>e.citta==="Cerignola"),matching.length?"Basati sulle categorie scelte e sui salvati.":"Non hai ancora preferenze: ecco gli eventi di Cerignola.");return;
  }
  if(action==="recent"){
   list(host,history.map(k=>all.find(e=>key(e)===k)).filter(Boolean),"Eventi aperti durante questa sessione. La cronologia non viene inviata al server.");
   const clear=mk("button","Cancella cronologia");clear.type="button";clear.onclick=()=>{history.length=0;run("recent",host);};host.append(clear);return;
  }
  if(action==="news"){
   const old=storageGet(newsKey),keys=all.map(key);
   const valid=Array.isArray(old)&&old.every(x=>typeof x==="string");
   list(host,valid?all.filter(e=>!old.includes(key(e))):[],valid?"Eventi aggiunti rispetto al tuo ultimo controllo.":"Primo controllo: salva la lista attuale per confrontarla in futuro.");
   const b=mk("button","Segna tutti come visti");b.type="button";b.onclick=()=>{mostraToast(storageSet(newsKey,keys)?"Controllo salvato sul dispositivo":"Salvataggio non disponibile");run("news",host);};host.append(b);host.append(mk("p","Non invia notifiche quando l'app è chiusa."));return;
  }
  if(action==="prefs"){
   host.append(mk("p","Scegli le categorie che preferisci. Restano solo sul tuo dispositivo."));
   const selected=new Set(prefs());
   for(const category of categories()){const b=mk("button",(selected.has(category)?"✓ ":"＋ ")+category);b.type="button";b.setAttribute("aria-pressed",String(selected.has(category)));b.onclick=()=>{selected.has(category)?selected.delete(category):selected.add(category);if(!storageSet(prefKey,[...selected])){mostraToast("Salvataggio non disponibile");return;}run("prefs",host);};host.append(b);}
   return;
  }
  if(action==="popular"){
   // Letture limitate e nessuna scrittura aggiuntiva. Campione dei primi 20 eventi entro 7 giorni.
   const sample=all.filter(entroSetteGiorni).slice(0,20);
   host.append(mk("p","Consultazione dei contatori pubblici dei prossimi 20 eventi entro 7 giorni…"));
   const rows=[];
   for(let i=0;i<sample.length;i+=4){if(seq!==generation||!active)return;const batch=sample.slice(i,i+4);const values=await Promise.all(batch.map(e=>window.CsfMetrics?.readPublicStats?.(e)));batch.forEach((e,j)=>{if(values[j]?.enabled&&values[j].open>0)rows.push({ev:e,n:values[j].open});});}
   if(seq!==generation||!active)return;
   rows.sort((a,b)=>b.n-a.n);
   host.replaceChildren(mk("p","Più aperti tra i "+sample.length+" prossimi eventi consultati (totali dall'attivazione, non visitatori unici)."));
   if(!rows.length)host.append(mk("p","Non ci sono ancora dati sufficienti per una classifica."));
   for(const {ev,n} of rows.slice(0,maxResults)){const b=mk("button","");b.type="button";b.append(mk("strong",ev.titolo),mk("small",n+" aperture · "+ev.citta));b.onclick=()=>showEvent(ev);host.append(b);}
  }
 }
 function open(side,from){
  if(active&&!active.open)release(active);
  if(active||busy())return;
  previousFocus=from||document.activeElement;active=dialogs[side];generation++;
  active.querySelector(".csf-side-results").replaceChildren();
  active.showModal();document.documentElement.classList.add("csf-side-open");active.querySelector(".csf-side-close").focus();
 }
 for(const side of ["left","right"]){
  const d=mk("dialog","","csf-side-dialog");d.dataset.side=side;d.setAttribute("aria-labelledby","csf-side-title-"+side);
  const header=mk("div","","csf-side-head"),title=mk("h2",side==="left"?"Scopri il territorio":"Il tuo spazio");title.id="csf-side-title-"+side;
  const x=mk("button","×","csf-side-close");x.type="button";x.setAttribute("aria-label","Chiudi pannello");x.onclick=close;header.append(title,x);d.append(header);
  d.append(mk("p",side==="left"?"Scopri cosa fare, dove e quando.":"I tuoi eventi, preferenze e novità."));
  const m=mk("div","","csf-side-menu"),host=mk("div","","csf-side-results");host.setAttribute("aria-live","polite");
  for(const [action,label] of menu[side]){const b=mk("button",label);b.type="button";b.dataset.sideAction=action;b.onclick=()=>run(action,host);m.append(b);}
  d.append(m,host);document.body.append(d);dialogs[side]=d;
  d.addEventListener("click",e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
  d.addEventListener("cancel",e=>{e.preventDefault();close();});
  d.addEventListener("close",()=>{if(!d.open)release(d);});
  $("csf-open-"+side)?.addEventListener("click",e=>open(side,e.currentTarget));
 }
 // Linguette visibili, con area tattile da 44px e apertura anche con un singolo tocco.
 let ultimoSwipe=0;
 for(const side of ["left","right"]){
  const area=mk("button","","csf-side-swipe");area.type="button";area.dataset.side=side;
  const label=side==="left"?"Scopri":"Il mio spazio";
  area.setAttribute("aria-label",side==="left"?"Apri Scopri il territorio":"Apri Il tuo spazio");
  area.setAttribute("aria-haspopup","dialog");
  area.append(mk("span",side==="left"?"› "+label:label+" ‹","csf-side-grip"));
  area.addEventListener("click",()=>{if(Date.now()-ultimoSwipe>500)open(side,area);});
  document.body.append(area);
 }
 document.addEventListener("touchstart",e=>{
  if(e.touches.length!==1||innerWidth>900){gesture=null;return;}
  if(active&&!active.open)release(active);
  const t=e.touches[0],x=t.clientX,y=t.clientY,w=document.documentElement.clientWidth;
  const strip=e.target.closest(".csf-side-swipe");
  if(!strip&&e.target.closest("input,textarea,select,button,a,summary,[contenteditable=true]")){gesture=null;return;}
  const side=active?active.dataset.side:(!busy()&&(strip?.dataset.side||(x>=8&&x<=65?"left":x>=w-65&&x<=w-8?"right":null)));
  gesture=side?{side,x,y,closing:!!active,time:Date.now(),horizontal:false}:null;
 },{passive:true});
 document.addEventListener("touchmove",e=>{
  const g=gesture;if(!g||e.touches.length!==1)return;
  const t=e.touches[0],dx=t.clientX-g.x,dy=t.clientY-g.y;
  if(!g.horizontal&&Math.abs(dy)>18&&Math.abs(dy)>Math.abs(dx)){gesture=null;return;}
  if(Math.abs(dx)>12&&Math.abs(dx)>Math.abs(dy)*1.3)g.horizontal=true;
  if(g.horizontal&&e.cancelable)e.preventDefault();
 },{passive:false});
 document.addEventListener("touchcancel",()=>{gesture=null;},{passive:true});
 document.addEventListener("touchend",e=>{
  const g=gesture;gesture=null;if(!g||e.changedTouches.length!==1||Date.now()-g.time>1800)return;
  const t=e.changedTouches[0],dx=t.clientX-g.x,dy=t.clientY-g.y;
  if(Math.abs(dx)<36||Math.abs(dx)<Math.abs(dy)*1.3)return;
  ultimoSwipe=Date.now();
  if(g.closing){if(g.side==="left"?dx<0:dx>0)close();}
  else if(g.side==="left"?dx>0:dx<0)open(g.side);
 },{passive:true});
 // Solo aperture vere: la sessione non viene salvata o trasmessa.
 document.addEventListener("toggle",e=>{const el=e.target;if(el.matches?.("#events-container details[data-event-key]")&&el.open){const k=el.dataset.eventKey;const i=history.indexOf(k);if(i>=0)history.splice(i,1);history.unshift(k);history.length=Math.min(history.length,30);}},true);
})();

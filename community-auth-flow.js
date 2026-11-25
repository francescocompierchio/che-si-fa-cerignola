/* OpenID Connect: solo ID token, nessun popup, stato e nonce monouso. */
(function(root){
  "use strict";
  const CALLBACK="https://francescocompierchio.github.io/che-si-fa-cerignola/community-accesso.html";
  const HOME="https://francescocompierchio.github.io/che-si-fa-cerignola/?community=1";
  const KEY="csfc_oidc_attempt_v1";
  const MAX_AGE=10*60*1000;
  const issuer="https://accounts.google.com";
  function random(crypto){
    return Array.from(crypto.getRandomValues(new Uint8Array(32)),x=>x.toString(16).padStart(2,"0")).join("");
  }
  function start(clientId,storage,crypto,now=Date.now()){
    if(!/^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$/.test(clientId||""))throw Error("config");
    const state=random(crypto),nonce=random(crypto);
    storage.setItem(KEY,JSON.stringify({state,nonce,created:now}));
    const url=new URL(issuer+"/o/oauth2/v2/auth");
    url.search=new URLSearchParams({client_id:clientId,redirect_uri:CALLBACK,response_type:"id_token",scope:"openid email profile",state,nonce,prompt:"select_account"}).toString();
    return url.toString();
  }
  function consume(fragment,clientId,storage,now=Date.now()){
    const p=new URLSearchParams(fragment.replace(/^#/,""));
    let saved;
    try{saved=JSON.parse(storage.getItem(KEY)||"null");}catch{throw Error("session");}
    if(!saved||typeof saved.created!=="number"||now-saved.created<0||now-saved.created>MAX_AGE||typeof saved.state!=="string"||p.getAll("state").length!==1||p.get("state")!==saved.state)throw Error("session");
    storage.removeItem(KEY);
    if(p.has("error"))throw Error("cancelled");
    const token=p.get("id_token");
    if(p.getAll("id_token").length!==1||!token||token.length>16000||!/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token))throw Error("credential");
    let claim;
    try{
      const segment=token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/");
      claim=JSON.parse(atob(segment.padEnd(Math.ceil(segment.length/4)*4,"=")));
    }catch{throw Error("credential");}
    if(!claim||claim.nonce!==saved.nonce||claim.aud!==clientId||
      ![issuer,"accounts.google.com"].includes(claim.iss)||claim.email_verified!==true||
      typeof claim.exp!=="number"||claim.exp*1000<=now||typeof claim.iat!=="number"||claim.iat*1000>now+60000||
      typeof claim.sub!=="string"||!claim.sub)throw Error("credential");
    // I claim qui sono solo controlli preliminari. Firma e identità devono essere
    // convalidate dal backend Firebase attraverso signInWithCredential.
    return token;
  }
  root.CsfCommunityOIDC=Object.freeze({CALLBACK,HOME,start,consume});
})(typeof window==="undefined"?globalThis:window);

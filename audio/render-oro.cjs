"use strict";
const fs=require("node:fs");
const assert=require("node:assert/strict");
const script=fs.readFileSync("event-page.js","utf8");
const first=script.indexOf("  function composition(context){");
const last=script.indexOf("  function running()",first);
assert.ok(first>=0&&last>first);
const compose=new Function(script.slice(first,last)+"\nreturn composition;")();
let channels,rate;
const buffer=compose({createBuffer(n,frames,hz){
  assert.equal(n,2);rate=hz;channels=Array.from({length:n},()=>new Float32Array(frames));
  return {getChannelData(i){return channels[i];}};
}});
assert.equal(rate,22050);
const frames=channels[0].length;
assert.equal(frames,180*rate);
const wav=Buffer.alloc(44+frames*4);
wav.write("RIFF",0);wav.writeUInt32LE(wav.length-8,4);wav.write("WAVEfmt ",8);wav.writeUInt32LE(16,16);
wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);
wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write("data",36);wav.writeUInt32LE(frames*4,40);
let peak=0;
for(let i=0;i<frames;i++)for(let c=0;c<2;c++){
  // Stesso guadagno del sintetizzatore Android, incorporato nel file per iOS.
  const x=channels[c][i]*.16*Math.min(1,i/(rate*.7));
  peak=Math.max(peak,Math.abs(x));
  wav.writeInt16LE(Math.round(Math.max(-1,Math.min(1,x))*32767),44+i*4+c*2);
}
assert.ok(peak>.005&&peak<.2,"Volume inatteso "+peak);
fs.writeFileSync(process.argv[2]||"/tmp/oro-al-tramonto.wav",wav);
console.log("Rendering originale: "+frames/rate+"s, picco "+peak);

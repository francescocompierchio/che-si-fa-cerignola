from PIL import Image, ImageDraw
from pathlib import Path
import json

src = Image.open("1795175413227~4.jpg").convert("RGB")
# Preserve the existing artwork; remove white corners with a rounded mask.
for name, size, inset in [("csf-icon-192-v3.png",192,0),("csf-icon-512-v3.png",512,0),("csf-maskable-512-v3.png",512,61)]:
    canvas=Image.new("RGB",(size,size),(7,55,105))
    width=size-2*inset
    logo=src.resize((width,width),Image.Resampling.LANCZOS)
    mask=Image.new("L",(width,width))
    ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,width-1),radius=round(width*.15),fill=255)
    canvas.paste(logo,(inset,inset),mask)
    canvas.save(name,optimize=True)
manifest=Path("manifest.json")
data=json.loads(manifest.read_text())
data["icons"]=[{"src":"csf-icon-192-v3.png","sizes":"192x192","type":"image/png","purpose":"any"},{"src":"csf-icon-512-v3.png","sizes":"512x512","type":"image/png","purpose":"any"},{"src":"csf-maskable-512-v3.png","sizes":"512x512","type":"image/png","purpose":"maskable"}]
manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
index=Path("index.html")
h=index.read_text()
h=h.replace('href="1795175413227~4.jpg" />','href="csf-icon-512-v3.png" />',1).replace('href="csf-icon-v2.svg" type="image/svg+xml"','href="csf-icon-192-v3.png" type="image/png"')
index.write_text(h)
sw=Path("sw.js")
s=sw.read_text().replace("chesifa-shell-v55","chesifa-shell-v56").replace('  new URL("csf-icon-v2.svg", self.registration.scope).href,\n  new URL("csf-icon-maskable-v2.svg", self.registration.scope).href','  new URL("csf-icon-192-v3.png", self.registration.scope).href,\n  new URL("csf-icon-512-v3.png", self.registration.scope).href,\n  new URL("csf-maskable-512-v3.png", self.registration.scope).href')
sw.write_text(s)
test=Path(".github/workflows/test-frontend.yml")
test.write_text(test.read_text().replace("chesifa-shell-v55","chesifa-shell-v56"))

import pathlib, subprocess, tempfile, urllib.request, json

TRACKS = [["USUAN1200054","https://incompetech.com/music/royalty-free/mp3-royaltyfree/Groove%20Grove.mp3",206],["USUAN1300033","https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clean%20Soul.mp3",307],["USUAN1100757","https://incompetech.com/music/royalty-free/mp3-royaltyfree/Windswept.mp3",208],["USUAN2400001","https://incompetech.com/music/royalty-free/mp3-royaltyfree/That%20Zen%20Moment.mp3",602],["USUAN1800019","https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dream%20Catcher.mp3",377]]
DEST = pathlib.Path("audio")
DEST.mkdir(exist_ok=True)
for ident, url, expected in TRACKS:
    dest = DEST / (ident + ".mp3")
    if dest.exists():
        continue
    with tempfile.TemporaryDirectory() as tmp:
        original = pathlib.Path(tmp) / "original.mp3"
        req = urllib.request.Request(url, headers={"User-Agent": "CheSiFaCerignola/1.0 (CC BY music import)"})
        with urllib.request.urlopen(req, timeout=60) as response, original.open("wb") as out:
            total = 0
            while chunk := response.read(65536):
                total += len(chunk)
                if total > 40*1024*1024: raise ValueError("Audio troppo grande")
                out.write(chunk)
        probe = json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(original)]))
        duration = float(probe["format"]["duration"])
        if not any(x.get("codec_type")=="audio" for x in probe["streams"]) or abs(duration-expected)>12:
            raise ValueError(f"File o durata inattesi: {ident}, {duration}")
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(original),"-map","0:a:0","-vn","-map_metadata","0","-c:a","libmp3lame","-b:a","96k",str(dest)],check=True)
        print(ident, duration, dest.stat().st_size)

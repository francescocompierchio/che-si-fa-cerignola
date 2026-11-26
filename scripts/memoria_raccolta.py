"""Salva la memoria del motore su un ramo Git dedicato ai dati operativi."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

BRANCH = "stato-motore-eventi"
REF = f"refs/heads/{BRANCH}"
LOCAL = Path(".csf-state/fonti.json")
NAME = "fonti.json"
MAX_BYTES = 2_000_000


def git(*args, data=None, check=True):
    return subprocess.run(
        ["git", *args], input=data, stdout=subprocess.PIPE, check=check,
    )


def leggi(data):
    if not data or len(data) > MAX_BYTES:
        return None
    try:
        stato = json.loads(data)
        timestamp = datetime.fromisoformat(stato["aggiornatoAl"])
        if not isinstance(stato["fonti"], dict) or timestamp.utcoffset() is None:
            return None
        return timestamp
    except (KeyError, TypeError, ValueError):
        return None


def locale():
    if LOCAL.is_file() and LOCAL.stat().st_size <= MAX_BYTES:
        return LOCAL.read_bytes()
    return b""


def remoto():
    ricerca = git("ls-remote", "--exit-code", "origin", REF, check=False)
    if ricerca.returncode == 2:
        return "", b""
    ricerca.check_returncode()
    git("fetch", "--quiet", "--no-tags", "origin", REF)
    parent = git("rev-parse", "FETCH_HEAD").stdout.decode().strip()
    return parent, git("show", f"{parent}:{NAME}").stdout


def ripristina():
    _, checkpoint = remoto()
    archivio = leggi(checkpoint)
    cache = leggi(locale())
    if archivio and (not cache or archivio > cache):
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        tmp = LOCAL.with_suffix(".checkpoint")
        tmp.write_bytes(checkpoint)
        tmp.replace(LOCAL)
        print("Memoria fonti ripristinata dal ramo tecnico.")


def salva():
    contenuto = locale()
    attuale = leggi(contenuto)
    if not attuale:
        raise ValueError("Memoria locale assente, non valida o oltre il limite")
    parent, checkpoint = remoto()
    precedente = leggi(checkpoint)
    if precedente and attuale - precedente < timedelta(hours=24):
        return
    blob = git("hash-object", "-w", "--stdin", data=contenuto).stdout.decode().strip()
    tree = git("mktree", data=f"100644 blob {blob}\t{NAME}\n".encode()).stdout.decode().strip()
    identita = ["-c", "user.name=CheSiFa Bot", "-c", "user.email=bot@users.noreply.github.com"]
    parents = ["-p", parent] if parent else []
    commit = git(*identita, "commit-tree", tree, *parents, "-m", "Salva memoria giornaliera del motore").stdout.decode().strip()
    git("push", "--quiet", "origin", f"{commit}:{REF}")
    data = attuale.astimezone(timezone.utc).date()
    print(f"Memoria fonti salvata per il {data} UTC.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("azione", choices=("ripristina", "salva"))
    args = parser.parse_args()
    {"ripristina": ripristina, "salva": salva}[args.azione]()

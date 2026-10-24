#!/usr/bin/env python3
"""Mide lo que SRS no reporta: FPS reales, nivel de audio y miniatura de cada stream activo.

Lee la lista de streams de la API de SRS y, por cada publicador activo, abre el
HTTP-FLV unos segundos con ffprobe/ffmpeg. Escribe en OUT_DIR:
  <stream>.json  fps medido, audio (presente / nivel dB / estado), timestamp
  <stream>.jpg   miniatura del último frame
El monitor (nginx) sirve OUT_DIR en /probe/.
"""
import json
import os
import re
import subprocess
import time
import urllib.request

SRS_API = os.environ.get("SRS_API", "http://srs:1985/api/v1/streams/")
SRS_HTTP = os.environ.get("SRS_HTTP", "http://srs:8080")
OUT_DIR = os.environ.get("OUT_DIR", "/srv/probe")
INTERVAL = int(os.environ.get("PROBE_INTERVAL", "15"))
SAMPLE_SECONDS = 4
# El nombre llega de un publicador sin autenticar: solo se sondea lo que es seguro en una URL/ruta.
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Umbrales sobre el pico (max_volume). Voz hablada sana ronda -6 a -3 dB.
PEAK_SILENT_DB = -50.0
PEAK_LOW_DB = -18.0


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def active_streams():
    with urllib.request.urlopen(SRS_API, timeout=5) as r:
        data = json.load(r)
    out = []
    for s in data.get("streams", []):
        name = s.get("name", "")
        if s.get("app") != "live" or not (s.get("publish") or {}).get("active"):
            continue
        if not SAFE_NAME.match(name):
            continue
        out.append({"name": name, "has_audio": bool(s.get("audio"))})
    return out


def measure_fps(url):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "packet=pts_time", "-of", "csv=p=0",
        "-read_intervals", f"%+{SAMPLE_SECONDS}", url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=SAMPLE_SECONDS + 10)
    pts = []
    for line in r.stdout.splitlines():
        try:
            pts.append(float(line.split(",")[0]))
        except ValueError:
            continue
    pts.sort()
    if len(pts) < 3 or pts[-1] - pts[0] <= 0:
        return None
    return round((len(pts) - 1) / (pts[-1] - pts[0]), 1)


def thumb_and_audio(url, name, has_audio):
    tmp = os.path.join(OUT_DIR, f".{name}.jpg")
    cmd = [
        "ffmpeg", "-v", "info", "-t", str(SAMPLE_SECONDS), "-i", url,
        "-map", "0:v:0", "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "6", "-f", "image2", "-y", tmp,
    ]
    if has_audio:
        cmd += ["-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=SAMPLE_SECONDS + 10)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, os.path.join(OUT_DIR, f"{name}.jpg"))
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", r.stderr)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", r.stderr)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def audio_status(has_audio, peak):
    if not has_audio:
        return "absent"
    if peak is None:
        return "unknown"
    if peak <= PEAK_SILENT_DB:
        return "silent"
    if peak <= PEAK_LOW_DB:
        return "low"
    return "ok"


def probe(stream):
    name = stream["name"]
    url = f"{SRS_HTTP}/live/{name}.flv"
    fps = measure_fps(url)
    mean, peak = thumb_and_audio(url, name, stream["has_audio"])
    result = {
        "name": name,
        "ts": int(time.time() * 1000),
        "fps": fps,
        "audio": {
            "present": stream["has_audio"],
            "status": audio_status(stream["has_audio"], peak),
            "mean_db": mean,
            "peak_db": peak,
        },
    }
    tmp = os.path.join(OUT_DIR, f".{name}.json")
    with open(tmp, "w") as f:
        json.dump(result, f)
    os.replace(tmp, os.path.join(OUT_DIR, f"{name}.json"))
    return result


def cleanup(active_names):
    for fn in os.listdir(OUT_DIR):
        if fn.startswith("."):
            continue
        base, ext = os.path.splitext(fn)
        if ext in (".json", ".jpg") and base not in active_names:
            os.remove(os.path.join(OUT_DIR, fn))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    log(f"probe: {SRS_API} cada {INTERVAL}s -> {OUT_DIR}")
    while True:
        started = time.time()
        try:
            streams = active_streams()
            cleanup({s["name"] for s in streams})
            for s in streams:
                try:
                    res = probe(s)
                    log(f"{s['name']}: fps={res['fps']} audio={res['audio']['status']} peak={res['audio']['peak_db']}")
                except Exception as e:  # un stream caído no debe parar a los demás
                    log(f"{s['name']}: error {e!r}")
        except Exception as e:
            log(f"error consultando SRS: {e!r}")
        time.sleep(max(1, INTERVAL - (time.time() - started)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Creative Review — prepara vídeos de anúncio para leitura.

Para cada vídeo gera, em <out>/<slug>/:
  manifest.json      duração, resolução, orientação, cortes, ritmo, lista de arquivos
  transcript.json    segmentos com timestamp (faster-whisper local)
  transcript.md      "[MM:SS–MM:SS] fala" — uma linha por segmento
  hook/              quadros individuais de 0.0s a 3.0s (a cada 0.5s)
  sheets/            folhas 3x2 com timestamp em cada quadro (resto do vídeo)

Uso:
  python prepare.py <video|pasta|url> [...] --out <pasta> [--interval 1.5] [--model small]
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
SCENE_THRESHOLD = 0.3
MAX_BODY_FRAMES = 120  # teto pra vídeos longos (VSL): o intervalo cresce sozinho


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def mmss(t):
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}" if t % 1 else f"{int(t // 60):02d}:{int(t % 60):02d}"


def slugify(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s[:60] or "video"


def collect_inputs(items, dl_dir):
    videos = []
    for item in items:
        if item.startswith("http://") or item.startswith("https://"):
            if "facebook.com/ads/library" in item:
                print(f"[!] {item}\n    Link da Ad Library: baixe antes com a skill fb-ad-library-spy.", file=sys.stderr)
                continue
            dl_dir.mkdir(parents=True, exist_ok=True)
            name = slugify(Path(item.split("?")[0]).stem) + ".mp4"
            dest = dl_dir / name
            print(f"[↓] baixando {item}")
            req = urllib.request.Request(item, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
                f.write(r.read())
            videos.append(dest)
            continue
        p = Path(item).expanduser()
        if p.is_dir():
            videos += sorted(x for x in p.rglob("*") if x.suffix.lower() in VIDEO_EXT)
        elif p.exists():
            videos.append(p)
        else:
            print(f"[!] não encontrado: {item}", file=sys.stderr)
    return videos


def probe(video):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(video)])
    info = json.loads(r.stdout or "{}")
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    w, h = v.get("width", 0), v.get("height", 0)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    fps = round(float(num) / float(den or 1), 2) if float(den or 1) else 0
    orient = "vertical" if h > w else "horizontal" if w > h else "quadrado"
    return {
        "duracao_segundos": round(float(info.get("format", {}).get("duration", 0)), 2),
        "resolucao": f"{w}x{h}", "orientacao": orient, "fps": fps,
        "tem_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def scene_cuts(video):
    r = run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
             f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", "-an", "-f", "null", "-"])
    return [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def grab(video, t, dest, height=960):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
         "-frames:v", "1", "-vf", f"scale=-2:{height}", "-q:v", "3", str(dest)])
    return dest.exists()


def build_sheets(frames, sheet_dir, cols=3, rows=2, tile_w=360):
    from PIL import Image, ImageDraw, ImageFont
    sheet_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    except Exception:
        font = ImageFont.load_default()
    sheets, per = [], cols * rows
    for i in range(0, len(frames), per):
        chunk = frames[i:i + per]
        imgs = [Image.open(p).convert("RGB") for _, p in chunk]
        tile_h = max(int(im.height * tile_w / im.width) for im in imgs)
        bar = 34
        sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + bar)), "white")
        draw = ImageDraw.Draw(sheet)
        for k, ((t, _), im) in enumerate(zip(chunk, imgs)):
            x, y = (k % cols) * tile_w, (k // cols) * (tile_h + bar)
            draw.rectangle([x, y, x + tile_w, y + bar], fill="black")
            draw.text((x + 8, y + 4), mmss(t), fill="yellow", font=font)
            sheet.paste(im.resize((tile_w, int(im.height * tile_w / im.width))), (x, y + bar))
        name = f"sheet_{len(sheets) + 1:02d}_{mmss(chunk[0][0]).replace(':', 'm')}-{mmss(chunk[-1][0]).replace(':', 'm')}.jpg"
        out = sheet_dir / name
        sheet.save(out, quality=85)
        sheets.append(str(out))
    return sheets


_model = None


def transcribe(video, work, model_name, lang):
    global _model
    wav = work / "audio.wav"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    if not wav.exists():
        return None, []
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[!] faster-whisper não instalado: sem transcrição", file=sys.stderr)
        return None, []
    if _model is None:
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = _model.transcribe(str(wav), language=lang, vad_filter=True, beam_size=5)
    out = [{"inicio": round(s.start, 2), "fim": round(s.end, 2), "texto": s.text.strip()} for s in segs]
    wav.unlink(missing_ok=True)
    return info.language, out


def process(video, out_root, interval, model_name, lang):
    slug = slugify(video.stem)
    work = out_root / slug
    work.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {video.name} → {work}")
    meta = probe(video)
    dur = meta["duracao_segundos"]

    # Hook: 0.0–3.0s a cada 0.5s, quadros individuais
    hook_dir = work / "hook"
    hook_dir.mkdir(exist_ok=True)
    hook = []
    t = 0.0
    while t <= min(3.0, dur - 0.05):
        dest = hook_dir / f"hook_{t:04.1f}s.jpg"
        if grab(video, t, dest):
            hook.append(str(dest))
        t += 0.5

    # Corpo: intervalo fixo + cortes de cena
    cuts = scene_cuts(video)
    step = max(interval, (dur - 3.0) / MAX_BODY_FRAMES) if dur > 3 else interval
    times, t = [], 3.0 + step
    while t < dur - 0.1:
        times.append(round(t, 2))
        t += step
    times += [c for c in cuts if c > 3.0]
    times.append(max(3.0, round(dur - 0.15, 2)))
    times = sorted(set(times))
    dedup = []
    for t in times:
        if not dedup or t - dedup[-1] >= 0.4:
            dedup.append(t)
    frame_dir = work / "frames"
    frame_dir.mkdir(exist_ok=True)
    frames = []
    for t in dedup:
        dest = frame_dir / f"f_{t:07.2f}s.jpg"
        if grab(video, t, dest, height=640):
            frames.append((t, dest))
    sheets = build_sheets(frames, work / "sheets") if frames else []

    # Transcrição
    language, segs = transcribe(video, work, model_name, lang) if meta["tem_audio"] else (None, [])
    (work / "transcript.json").write_text(json.dumps(
        {"idioma": language, "segmentos": segs}, ensure_ascii=False, indent=2))
    lines = [f"[{mmss(s['inicio'])}–{mmss(s['fim'])}] {s['texto']}" for s in segs]
    (work / "transcript.md").write_text("\n".join(lines) or "(sem fala detectada)")

    shots = [0.0] + cuts + [dur]
    shot_lens = [b - a for a, b in zip(shots, shots[1:]) if b > a]
    meta.update({
        "arquivo": str(video.resolve()),
        "slug": slug,
        "idioma_detectado": language,
        "cortes_detectados": len(cuts),
        "tempos_dos_cortes": cuts,
        "duracao_media_plano_s": round(sum(shot_lens) / len(shot_lens), 2) if shot_lens else dur,
        "intervalo_amostragem_s": round(step, 2),
        "hook_frames": hook,
        "sheets": sheets,
        "transcript": str(work / "transcript.md"),
    })
    (work / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"    {dur}s | {meta['orientacao']} | {len(cuts)} cortes | plano médio {meta['duracao_media_plano_s']}s"
          f" | {len(hook)} hook + {len(sheets)} folhas | {len(segs)} segmentos de fala")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=1.5)
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default=None, help="ex.: en, pt (padrão: autodetectar)")
    a = ap.parse_args()
    out_root = Path(a.out).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)
    videos = collect_inputs(a.inputs, out_root / "_downloads")
    if not videos:
        sys.exit("Nenhum vídeo para processar.")
    results = [process(v, out_root, a.interval, a.model, a.lang) for v in videos]
    (out_root / "lote.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nPronto: {len(results)} vídeo(s) em {out_root}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Creative Review — leitura de edição e retenção.

Mede o que a leitura de copy não enxerga: trechos sem fala, buracos de áudio, imagem parada, fala repetida,
salto de volume e ritmo por janela. Sai em <out>/<slug>/edicao.json + edicao.md, com os quadros de cada
trecho sem fala em gaps/.

O método de escuta (curva de nível, "stop-down" = queda de 20 dB abaixo do nível geral, aqui a partir de 0,6s,
começo e fim do arquivo tratados como entrada e cauda) segue o `earshot timeline` de Leon Lin
(github.com/Leonxlnx/earshot, MIT), reescrito aqui só com ffmpeg + numpy, sem modelo extra.
"""
import difflib
import json
import re
import subprocess

PAUSA_MIN = 0.8        # abaixo disso é respiro normal de fala
GRAVE = 4.0            # trecho sem fala a partir daqui é grave
RESPIRO = 0.4          # o que sobra de cada trecho depois do corte
ABERTURA_MAX = 1.0     # fala tem que entrar até aqui
MAX_QUADROS_GAP = 150


def _mmss(t):
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def _runs(mask, min_len):
    out, start = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def _fala(audio, sr):
    """intervalos de fala (s) pelo Silero VAD que já vem no faster-whisper"""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    opts = VadOptions(min_silence_duration_ms=300, speech_pad_ms=60, min_speech_duration_ms=200)
    return [(c["start"] / sr, c["end"] / sr) for c in get_speech_timestamps(audio, opts, sampling_rate=sr)]


def _envelope(audio, sr, hop_s=0.05, win_s=0.1):
    import numpy as np
    hop, win = int(sr * hop_s), int(sr * win_s)
    n = max(1, (len(audio) - win) // hop + 1)
    idx = np.arange(n)[:, None] * hop + np.arange(win)[None, :]
    idx = np.minimum(idx, len(audio) - 1)
    power = (audio[idx].astype("float64") ** 2).mean(axis=1)
    db = 10 * np.log10(np.maximum(power, 1e-10))
    return np.arange(n) * hop_s + win_s / 2, db


def _nivel(db, t, a, b):
    import numpy as np
    m = (t >= a) & (t <= b)
    if not m.any():
        return None
    return float(10 * np.log10(np.mean(10 ** (db[m] / 10))))


def _congelados(video):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "freezedetect=n=0.003:d=1.0",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    ini = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
    fim = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", r.stderr)]
    return list(zip(ini, fim + [1e9] * (len(ini) - len(fim))))


def _sobrepoe(a, b, intervalos):
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in intervalos)


def _norm(txt):
    return re.sub(r"[^a-z0-9à-ÿ ]+", "", txt.lower()).split()


def _repeticoes(segs, palavras):
    achados = []
    limpos = [(s, _norm(s["texto"])) for s in segs]
    for i, (a, wa) in enumerate(limpos):
        if len(wa) < 4:
            continue
        for b, wb in limpos[i + 1:]:
            if b["inicio"] - a["fim"] > 90:
                break
            if len(wb) >= 4 and difflib.SequenceMatcher(None, wa, wb).ratio() >= 0.85:
                achados.append({"tipo": "frase repetida", "primeira": a["inicio"], "segunda": b["inicio"],
                                "texto": b["texto"]})
    toks = [(p["inicio"], (_norm(p["texto"]) or [""])[0]) for p in palavras]
    toks = [x for x in toks if x[1]]
    i = 0
    while i < len(toks) - 7:
        gram = [w for _, w in toks[i:i + 4]]
        hit = next((j for j in range(i + 2, min(i + 13, len(toks) - 3))
                    if [w for _, w in toks[j:j + 4]] == gram), None)
        if hit is not None and not any(abs(r["segunda"] - toks[hit][0]) < 3 for r in achados):
            achados.append({"tipo": "recomeço", "primeira": toks[i][0], "segunda": toks[hit][0],
                            "texto": " ".join(gram)})
            i = hit + 4
        else:
            i += 1
    return sorted(achados, key=lambda r: r["segunda"])


def analisar(video, wav, work, dur, cuts, segs, palavras, limite, grab, build_sheets):
    import numpy as np
    from faster_whisper.audio import decode_audio
    sr = 16000
    audio = decode_audio(str(wav), sampling_rate=sr)
    fala = _fala(audio, sr) if len(audio) > sr // 2 else []
    t, db = _envelope(audio, sr)
    ativos = db[db > -60]
    geral = float(10 * np.log10(np.mean(10 ** (ativos / 10)))) if len(ativos) else -90.0
    piso = max(-60.0, geral - 20.0)
    parados = _congelados(video)

    # buracos de áudio: tudo cai (fala, trilha e efeito), no padrão "stop-down" do earshot
    buracos = []
    for s, e in _runs(db < piso, 12):
        a, b = float(t[s]) - 0.05, float(t[e - 1]) + 0.05
        if a <= 0.1 or b >= dur - 0.1:
            continue
        buracos.append({"inicio": round(a, 2), "fim": round(b, 2), "duracao": round(b - a, 1)})

    # trechos sem fala = o que sobra entre os intervalos de fala
    bordas = [0.0] + [x for par in fala for x in par] + [dur]
    vaos = [(bordas[i], bordas[i + 1]) for i in range(0, len(bordas), 2)]
    trechos, pausas = [], 0.0
    for k, (a, b) in enumerate(vaos):
        d = b - a
        onde = "abertura" if k == 0 else "final" if k == len(vaos) - 1 else "meio"
        if not fala:
            onde = "vídeo inteiro"
        if d >= PAUSA_MIN:
            pausas += d
        minimo = ABERTURA_MAX if onde == "abertura" else limite
        if d < minimo:
            continue
        nivel = _nivel(db, t, a, b)
        mudo = nivel is None or nivel < piso + 3
        n_cortes = sum(1 for c in cuts if a < c < b)
        parado = _sobrepoe(a, b, parados)
        antes = " ".join(p["texto"] for p in palavras if p["fim"] <= a + 0.35)[-70:].strip()
        depois = " ".join(p["texto"] for p in palavras if p["inicio"] >= b - 0.35)[:70].strip()
        trechos.append({
            "inicio": round(a, 2), "fim": round(b, 2), "duracao": round(d, 1), "onde": onde,
            "gravidade": "grave" if d >= GRAVE else "atenção",
            "audio": "silêncio total" if mudo else "só trilha/efeito",
            "nivel_db_vs_geral": None if nivel is None else round(nivel - geral, 1),
            "cortes_dentro": n_cortes,
            "imagem_parada_s": round(parado, 1),
            "fala_antes": antes, "fala_depois": depois,
        })

    # quanto dá pra enxugar só fechando os trechos sem fala
    recuperavel = sum(max(0.0, x["duracao"] - RESPIRO) for x in trechos if x["onde"] != "vídeo inteiro")
    tempo_fala = sum(b - a for a, b in fala)

    # ritmo por janela
    jan = 30.0 if dur > 120 else 10.0
    janelas = []
    a = 0.0
    while a < dur - 1:
        b = min(dur, a + jan)
        n = sum(1 for p in palavras if a <= p["inicio"] < b)
        janelas.append({"inicio": round(a, 1), "fim": round(b, 1), "palavras_min": round(n / (b - a) * 60),
                        "fala_pct": round(100 * _sobrepoe(a, b, fala) / (b - a))})
        a = b
    cheias = sorted(j["palavras_min"] for j in janelas if j["fim"] - j["inicio"] >= jan * 0.6)
    mediana = cheias[len(cheias) // 2] if cheias else 0
    for j in janelas:
        j["lento"] = bool(mediana and j["fim"] - j["inicio"] >= jan * 0.6 and j["palavras_min"] < 0.6 * mediana)

    # volume da fala
    niveis = [(x, y, _nivel(db, t, x, y)) for x, y in fala if y - x >= 0.6]
    niveis = [n for n in niveis if n[2] is not None]
    saltos = []
    if len(niveis) >= 4:
        med = sorted(n[2] for n in niveis)[len(niveis) // 2]
        saltos = [{"inicio": round(x, 2), "fim": round(y, 2), "diferenca_db": round(v - med, 1)}
                  for x, y, v in niveis if abs(v - med) >= 6]

    # planos mais longos
    marcos = [0.0] + list(cuts) + [dur]
    planos = sorted(({"inicio": round(x, 2), "fim": round(y, 2), "duracao": round(y - x, 2)}
                     for x, y in zip(marcos, marcos[1:]) if y > x), key=lambda p: -p["duracao"])[:3]

    # quadros de dentro de cada trecho sem fala, pra julgar se a imagem segura sozinha
    gap_dir, quadros = work / "gaps", []
    if trechos:
        (work / "gaps_frames").mkdir(exist_ok=True)
        # 1 quadro a cada ~1,5s do trecho (trecho longo ganha mais quadros), com teto no total
        quer = [max(2, min(14, round(x["duracao"] / 1.5) + 1)) for x in trechos]
        escala = min(1.0, MAX_QUADROS_GAP / sum(quer))
        for x, q in zip(trechos, quer):
            n = max(2, round(q * escala))
            for i in range(n):
                tt = min(dur - 0.15, x["inicio"] + 0.2 + (x["duracao"] - 0.4) * i / (n - 1))
                dest = work / "gaps_frames" / f"g_{tt:07.2f}s.jpg"
                if grab(video, tt, dest, height=640):
                    quadros.append((round(tt, 2), dest))
    folhas = build_sheets(quadros, gap_dir) if quadros else []

    res = {
        "duracao_s": round(dur, 2),
        "limite_trecho_sem_fala_s": limite,
        "tempo_com_fala_s": round(tempo_fala, 1),
        "fala_pct": round(100 * tempo_fala / dur) if dur else 0,
        "palavras_min": round(len(palavras) / dur * 60) if dur else 0,
        "pausas_total_s": round(pausas, 1),
        "trechos_sem_fala": trechos,
        "tempo_recuperavel_s": round(recuperavel, 1),
        "duracao_enxuta_s": round(dur - recuperavel, 1),
        "buracos_de_audio": buracos,
        "repeticoes": _repeticoes(segs, palavras),
        "saltos_de_volume": saltos,
        "ritmo_janelas": janelas,
        "planos_mais_longos": planos,
        "imagem_parada": [{"inicio": round(x, 2), "fim": round(min(y, dur), 2)} for x, y in parados],
        "folhas_dos_trechos": folhas,
    }
    (work / "edicao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    (work / "edicao.md").write_text(_markdown(res, video.name))
    return res


def _markdown(r, nome):
    tr = r["trechos_sem_fala"]
    graves = [x for x in tr if x["gravidade"] == "grave"]
    L = [f"# Edição e retenção — {nome}", ""]
    corte = 100 * r["tempo_recuperavel_s"] / r["duracao_s"] if r["duracao_s"] else 0
    L.append(f"**Resumo:** {_mmss(r['duracao_s'])} de vídeo · fala em {r['fala_pct']}% do tempo · "
             f"{r['palavras_min']} palavras/min · {len(tr)} trecho(s) sem fala de {r['limite_trecho_sem_fala_s']}s "
             f"ou mais ({len(graves)} grave(s)) · fechando esses trechos o vídeo vai para "
             f"{_mmss(r['duracao_enxuta_s'])} (−{corte:.0f}%).")
    L += ["", "## Trechos sem fala", ""]
    if tr:
        L += ["| # | Tempo | Duração | Gravidade | Áudio | Imagem | Fala antes → fala depois |",
              "|---|---|---|---|---|---|---|"]
        for i, x in enumerate(tr, 1):
            img = f"{x['cortes_dentro']} corte(s)"
            if x["imagem_parada_s"] >= 1:
                img += f", {x['imagem_parada_s']}s de imagem parada"
            lugar = "" if x["onde"] == "meio" else f" ({x['onde']})"
            L.append(f"| {i} | {_mmss(x['inicio'])}–{_mmss(x['fim'])}{lugar} | {x['duracao']}s | {x['gravidade']} | "
                     f"{x['audio']} | {img} | \"…{x['fala_antes']}\" → \"{x['fala_depois']}…\" |")
        L += ["", "Quadros de dentro de cada trecho: pasta `gaps/`."]
    else:
        L.append("Nenhum.")
    L += ["", "## Buracos de áudio (fala, trilha e efeito caem juntos)", ""]
    L += [f"- {_mmss(b['inicio'])}–{_mmss(b['fim'])} ({b['duracao']}s)" for b in r["buracos_de_audio"]] or ["Nenhum."]
    L += ["", "## Fala repetida ou recomeço", ""]
    L += [f"- {_mmss(x['segunda'])} {x['tipo']} (já dita em {_mmss(x['primeira'])}): \"{x['texto']}\""
          for x in r["repeticoes"]] or ["Nenhuma."]
    L += ["", "## Salto de volume na fala", ""]
    L += [f"- {_mmss(s['inicio'])}–{_mmss(s['fim'])}: {s['diferenca_db']:+.1f} dB contra o resto"
          for s in r["saltos_de_volume"]] or ["Nenhum."]
    L += ["", "## Ritmo por janela", "", "| Janela | Palavras/min | Tempo com fala | |", "|---|---|---|---|"]
    L += [f"| {_mmss(j['inicio'])}–{_mmss(j['fim'])} | {j['palavras_min']} | {j['fala_pct']}% | "
          f"{'lento' if j['lento'] else ''} |" for j in r["ritmo_janelas"]]
    L += ["", "## Planos mais longos sem corte", ""]
    L += [f"- {_mmss(p['inicio'])}–{_mmss(p['fim'])} ({p['duracao']}s)" for p in r["planos_mais_longos"]]
    return "\n".join(L) + "\n"

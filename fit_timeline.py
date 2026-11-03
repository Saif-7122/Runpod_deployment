"""Fit the script to the measured voiceover: scene times, in-points inside approved segments, captions.

Writes timeline.json and captions.ass.
  python fit_timeline.py --run-dir workspace/runs/<run_id>
"""
import argparse
import json
import re
from pathlib import Path

from common import load_config, log, read_json, write_json
from judge import segment_index


def fit(cfg, script, audio_meta, catalog, run_dir):
    segs = segment_index(catalog)
    clips = catalog["clips"]
    gap = audio_meta.get("gap_seconds", 0.0)
    tail = cfg["rendering"].get("tail_seconds", 0.5)
    durs = {p["id"]: p["duration"] for p in audio_meta["sentences"]}

    cuts = read_json(cfg["_paths"]["catalog"] / "cuts.json", {})     # hidden cuts inside pre-edited clips (cutmap.py)
    sim_file = cfg["_paths"]["catalog"] / "similar.json"
    similar = read_json(sim_file, {})                                # per segment: span that still looks like the hero
    logo_file = cfg["_paths"]["catalog"] / "logos.json"
    logos = read_json(logo_file, {})                                 # per segment: Oxygen Forest logo already burned in?
    xf = float(cfg["rendering"].get("transition_seconds", 0))
    scenes, voice, t = [], [], 0.0
    sents = script["sentences"]
    for k, s in enumerate(sents):
        d = durs[s["id"]]
        voice.append({"id": s["id"], "text": s["text"], "sub": s.get("sub", ""),
                      "start": round(t, 3), "end": round(t + d, 3)})
        window = d + (gap if k < len(sents) - 1 else tail)
        ids = s["segment_ids"]
        piece = window / len(ids)
        for j, sid in enumerate(ids):
            at = (s.get("src_in") or {}).get(str(j))                # hand-picked start second inside the clip
            seg = segs[sid]
            start = t + j * piece
            usable = seg["out"] - seg["in"]
            clip_len = clips[seg["file_id"]].get("duration_s") or seg["out"]
            run = clean_run(cuts.get(seg["file_id"]), clip_len, seg)
            if run and len(cuts.get(seg["file_id"]) or []) >= 2:      # pre-edited clip: also stop at dissolves / pans
                if sid not in similar:
                    from cutmap import similar_span
                    src = clips[seg["file_id"]].get("proxy") or clips[seg["file_id"]].get("local_path")
                    similar[sid] = similar_span(src, seg["hero_second"], run[0], run[1]) if src else run
                run = (max(run[0], similar[sid][0]), min(run[1], similar[sid][1]))
            if at is not None:
                src_in, hold = min(float(at), max(0.0, clip_len - piece - 0.1)), 0.0
            elif seg.get("native_audio"):                          # picture locked to its own audio
                src_in, hold = seg["in"], max(0.0, piece - usable)
            elif run:                                              # stay inside one uncut stretch of the source
                need = piece + xf
                # pre-edited clips also hide soft dissolves the cut map can't see: start right on the checked frame
                edited = len(cuts.get(seg["file_id"]) or []) >= 2
                ideal = seg["hero_second"] - (0.15 if edited else piece * 0.35)
                src_in = min(max(ideal, run[0]), max(run[0], run[1] - need))
                hold = max(0.0, need - (run[1] - src_in))
            elif usable >= piece:
                ideal = seg["hero_second"] - piece * 0.35          # hero lands early in the cut
                src_in = min(max(ideal, seg["in"]), seg["out"] - piece)
                hold = 0.0
            else:
                src_in, hold = seg["in"], piece - usable           # render holds the last frame
            clip = clips[seg["file_id"]]
            scenes.append({
                "scene": len(scenes) + 1, "sentence": s["id"],
                "start_time": round(start, 3), "end_time": round(start + piece, 3), "duration": round(piece, 3),
                "segment_id": sid, "clip_file_id": seg["file_id"], "clip_name": clip["name"],
                "source_path": clip.get("proxy") or clip.get("local_path"),
                "source_is_proxy": bool(clip.get("proxy")),
                "original_path": clip.get("local_path"),          # local footage folders: render from the original
                "source_in": round(src_in, 3), "hold_seconds": round(hold, 3),
                "crop_focus_x": seg.get("subject_x", 0.5),
                "text_overlay": s.get("overlay", "") if j == 0 else "",
                "caption_style": s.get("caption_style", "normal"),
                "native_audio": bool(seg.get("native_audio")),
                "burned_captions": bool(clip.get("has_burned_captions")),
                "burned_logo": burned_logo(cfg, logos, clip, seg),
                "description": seg.get("description", ""),
            })
        t += window

    write_json(sim_file, similar)
    write_json(logo_file, logos)
    timeline = {
        "run_id": Path(run_dir).name, "video_title": script.get("video_title", ""),
        "language": script.get("language", "en"), "theme": script.get("theme"), "mode": script.get("mode", "voice"),
        "angle": script.get("angle", ""), "project": script.get("project"),
        "total_duration_seconds": round(t, 3), "voiceover_audio": "voiceover.wav",
        "voiceover": voice, "timeline": scenes, "missing_shots": script.get("missing_shots", []),
    }
    write_json(Path(run_dir) / "timeline.json", timeline)
    write_captions(cfg, timeline, sents, Path(run_dir) / "captions.ass")
    log("fit", f"{len(scenes)} cuts over {t:.1f} s")
    return timeline


# ------------------------------------------------------------------ captions (ASS)

def burned_logo(cfg, cache, clip, seg):
    """Does this shot already carry the Oxygen Forest logo? Then the render hides ours so it never shows twice.
    The site-visit compilations were all branded by the team (red box or a big, often faded flower mark that a
    detector misses), raw DJI / phone clips are not; anything else goes through the detector."""
    if clip.get("project") in (cfg["captions"].get("logo") or {}).get("branded_projects", []):
        return True
    sid = seg["segment_id"]
    if sid not in cache:
        from cutmap import has_burned_logo
        src = clip.get("proxy") or clip.get("local_path")
        cache[sid] = bool(src and has_burned_logo(src, seg["hero_second"])[0])
    return cache[sid]


def clean_run(cut_times, clip_len, seg, margin=0.1):
    """The uncut stretch of the clip around the segment (cuts known from cutmap.py), trimmed by a small margin."""
    if cut_times is None:
        return None
    bounds = [0.0] + [x for x in cut_times if 0 < x < clip_len] + [clip_len]
    anchor = seg.get("hero_second") or (seg["in"] + seg["out"]) / 2
    for a, b in zip(bounds, bounds[1:]):
        if a <= anchor < b:
            return (a + (margin if a > 0 else 0.0), b - margin)
    return None


def ts(x):
    cs = int(round(x * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(text):
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def ass_color(hex_rgb, alpha=0):
    """#RRGGBB -> ASS &HAABBGGRR (alpha 0 = opaque, 255 = invisible)."""
    h = hex_rgb.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def rounded_rect(x0, y0, x1, y1, r):
    k = r * 0.45
    return (f"m {x0 + r} {y0} l {x1 - r} {y0} b {x1 - k} {y0} {x1} {y0 + k} {x1} {y0 + r} "
            f"l {x1} {y1 - r} b {x1} {y1 - k} {x1 - k} {y1} {x1 - r} {y1} "
            f"l {x0 + r} {y1} b {x0 + k} {y1} {x0} {y1 - k} {x0} {y1 - r} "
            f"l {x0} {y0 + r} b {x0} {y0 + k} {x0 + k} {y0} {x0 + r} {y0}")


def word_chunks(words, max_words, max_chars):
    """Group words into on-screen chunks: <= max_words and <= max_chars, breaking after punctuation."""
    out, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(trial) > max_chars):
            out.append(cur)
            cur = []
        cur.append(w)
        if w[-1:] in ".,!?;:—" and len(cur) >= 2:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def word_times(words, start, end):
    """Spread a sentence's measured duration over its words by spoken weight (letters + a pause after punctuation)."""
    wts = [max(2, len(re.sub(r"\W", "", w))) + (3 if w[-1:] in ".,!?;:" else 0) for w in words]
    span, t, out = end - start, start, []
    for w, k in zip(words, wts):
        d = span * k / sum(wts)
        out.append((t, t + d))
        t += d
    return out


def stress_flags(words):
    """*Stressed phrases* (markers may span words) -> [(clean word, stressed?)]."""
    out, on = [], False
    for w in words:
        out.append((w.replace("*", ""), on or "*" in w))
        if w.count("*") % 2:
            on = not on
    return out


def rupee(text, font):
    # several display fonts have no rupee sign: draw it in Poppins inline
    return text.replace("₹", "{\\fnPoppins SemiBold}₹{\\fn" + font + "}")


def styled(flags, font, size, colour, em, highlight=None, hl_colour=None):
    """ASS text for a run of words; stressed words switch to the theme's emphasis font, colour and size."""
    parts = []
    for i, (w, hot) in enumerate(flags):
        if hot:
            f, s, col = em["font"], int(size * em["scale"]), ass_color(em["color"])
        else:
            f, s, col = font, size, (hl_colour if i == highlight else colour)
        parts.append("{\\fn" + f + "\\fs" + str(s) + "\\c" + col + "}" + rupee(esc(w), f))
    return " ".join(parts)


def headline_text(text, c, em):
    return styled(stress_flags(text.split()), c["headline"]["font"], c["headline"]["size"],
                  ass_color(c["palette"]["text"]), em)


def write_captions(cfg, timeline, sents, path):
    import copy
    c = copy.deepcopy(cfg["captions"])
    lang_over = (c.get("languages") or {}).get(timeline.get("language", "en"), {})
    for part in ("caption", "headline"):                 # e.g. Telugu -> Noto Sans Telugu
        c[part].update(lang_over.get(part, {}))
    th = (c.get("themes") or {}).get(timeline.get("theme") or "", {})
    for part in ("caption", "headline"):                 # the reel's type theme wins
        c[part].update(th.get(part, {}))
    em = {"font": c["headline"]["font"], "color": c["palette"]["accent"], "scale": 1.3, **th.get("emph", {})}
    pal, cap, hd, ec = c["palette"], c["caption"], c["headline"], c["end_card"]
    W, H = 1080, 1920
    side = int(W * c["safe_zone"]["sides"])
    text_c, acc_c, ink_c = ass_color(pal["text"]), ass_color(pal["accent"]), ass_color(pal["shadow"], 0x40)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{cap['font']},{cap['size']},{text_c},{text_c},{ink_c},{ass_color(pal['shadow'], 0x70)},0,0,0,0,100,100,0,0,1,{cap['outline']},{cap['shadow']},5,{side},{side},0,1
Style: Headline,{hd['font']},{hd['size']},{text_c},{text_c},{ass_color(pal['shadow'], 0x60)},{ass_color(pal['shadow'], 0x60)},0,0,0,0,100,100,0,0,1,2,{hd['shadow']},8,{side},{side},0,1
Style: Card,{ec.get('font', 'Fraunces SemiBold')},104,{text_c},{text_c},{ink_c},{ink_c},0,0,0,0,100,100,0,0,1,0,0,5,{side},{side},0,1
Style: CardSub,{cap['font'].replace('SemiBold', 'Medium')},34,{text_c},{text_c},{ink_c},{ink_c},0,0,0,0,100,100,2,0,1,0,0,5,{side},{side},0,1
Style: CardCta,{cap['font']},44,{text_c},{text_c},{ink_c},{ink_c},0,0,0,0,100,100,0,0,1,0,0,5,{side},{side},0,1
Style: Shape,{cap['font']},10,{ink_c},{ink_c},{ink_c},{ink_c},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    total = timeline["total_duration_seconds"]
    card_t = max(0.0, total - ec["seconds"])
    by_id = {s["id"]: s for s in sents}
    y = cap["y_center"]

    scenic = timeline.get("mode") == "scenic"
    wm = c.get("wordmark") or {}
    if wm.get("text"):                                # small brand mark, top left (many clips carry the logo top right)
        ev.append(f"Dialogue: 3,{ts(0.3)},{ts(card_t)},Caption,,0,0,0,,{{\\an7\\pos({side},120)\\fn{wm['font']}"
                  f"\\fs{wm['size']}\\bord2\\shad2\\alpha&H10&\\fad(400,300)}}{esc(wm['text'])}")

    # 1a) scenic reels: one big text card per line (main words + small fact line), no voice
    for v in (timeline["voiceover"] if scenic else []):
        if v["start"] >= card_t:
            continue
        end = min(v["end"], card_t)
        main = styled(stress_flags(v["text"].split()), hd["font"], hd["size"], text_c, em)
        sub = ("\\N{\\fn" + cap["font"] + "\\fs54\\c" + ass_color(pal["accent"]) + "}" + rupee(esc(v["sub"]), cap["font"])) \
            if v.get("sub") else ""
        band = f"m 0 470 l {W} 470 l {W} 900 l 0 900"
        ev.append(f"Dialogue: 0,{ts(v['start'] + 0.15)},{ts(end)},Shape,,0,0,0,,"
                  f"{{\\an7\\pos(0,0)\\1c{ass_color(pal['shadow'])}\\1a&HA0&\\blur70\\fad(300,250)\\p1}}{band}{{\\p0}}")
        ev.append(f"Dialogue: 2,{ts(v['start'] + 0.15)},{ts(end)},Headline,,0,0,0,,"
                  f"{{\\an5\\move(540,700,540,680,0,350)\\fad(300,250)\\q1}}{main}{sub}")

    # 1b) spoken captions: chunk on screen, current word in the accent colour, gentle pop-in per chunk;
    #     *stressed* words in the theme's emphasis font, colour and size
    for v in ([] if scenic else timeline["voiceover"]):
        s = by_id[v["id"]]
        if any(sc["sentence"] == v["id"] and sc.get("burned_captions") and sc.get("native_audio")
               for sc in timeline["timeline"]):
            continue                                                 # clip already has its own captions
        flags = stress_flags(v["text"].split())
        words = [w for w, _ in flags]
        times = word_times(words, v["start"], v["end"])
        size = int(cap["size"] * (1.1 if s.get("caption_style") == "hook" else 1.0))
        k = 0
        for chunk in word_chunks(words, cap["max_words"], cap["max_chars_per_line"]):
            c0, c1 = times[k][0], times[k + len(chunk) - 1][1]
            c1 = max(c1, c0 + cap["min_seconds"])
            if c0 >= card_t:                                         # end card owns the screen
                break
            c1 = min(c1, card_t)
            if th.get("phrase"):                                     # reference-reel look: calm phrase, soft fade,
                txt = styled(flags[k:k + len(chunk)], cap["font"], size, text_c, em)   # stressed word in serif
                ev.append(f"Dialogue: 2,{ts(c0)},{ts(c1)},Caption,,0,0,0,,"
                          f"{{\\an5\\pos(540,{y})\\fad(160,120)\\blur0.6}}{txt}")
                k += len(chunk)
                continue
            for j, w in enumerate(chunk):
                w0 = times[k + j][0]
                w1 = times[k + j + 1][0] if j + 1 < len(chunk) else c1
                if w0 >= c1:
                    break
                pop = "\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)" if j == 0 else ""
                txt = styled(flags[k:k + len(chunk)], cap["font"], size, text_c, em, highlight=j, hl_colour=acc_c)
                ev.append(f"Dialogue: 2,{ts(w0)},{ts(min(w1, c1))},Caption,,0,0,0,,"
                          f"{{\\an5\\pos(540,{y})\\blur1.2{pop}}}{txt}")
            k += len(chunk)

    # 2) headlines: one per overlay, fade-up under the top safe band
    # scenic cards already carry the words; with burned captions a top heading is clutter (user, 2026-10-30)
    for sc in ([] if scenic or not c.get("headlines", True) else timeline["timeline"]):
        if sc["text_overlay"]:
            end = max(x["end_time"] for x in timeline["timeline"] if x["sentence"] == sc["sentence"])
            if sc["start_time"] >= card_t:
                continue
            end = min(end, card_t)
            y0 = hd["y_top"]
            band = f"m 0 {y0 - 140} l {W} {y0 - 140} l {W} {y0 + 230} l 0 {y0 + 230}"
            ev.append(f"Dialogue: 0,{ts(sc['start_time'] + 0.1)},{ts(end)},Shape,,0,0,0,,"
                      f"{{\\an7\\pos(0,0)\\1c{ass_color(pal['shadow'])}\\1a&H9A&\\blur60\\fad(280,200)\\p1}}{band}{{\\p0}}")
            ev.append(f"Dialogue: 1,{ts(sc['start_time'] + 0.1)},{ts(end)},Headline,,0,0,0,,"
                      f"{{\\an8\\move(540,{y0 + 24},540,{y0},0,280)\\fad(280,200)}}{headline_text(sc['text_overlay'], c, em)}")

    # 3) end card: dim the whole frame, brand in serif, blush rule, maroon CTA pill, contact line
    if ec.get("brand"):
        t0 = card_t
        full = f"m 0 0 l {W} 0 l {W} {H} l 0 {H}"
        ev.append(f"Dialogue: 5,{ts(t0)},{ts(total)},Shape,,0,0,0,,{{\\an7\\pos(0,0)\\1c{ass_color(pal['shadow'])}\\1a&H55&\\fad(400,0)\\p1}}{full}{{\\p0}}")
        ev.append(f"Dialogue: 6,{ts(t0 + 0.15)},{ts(total)},Card,,0,0,0,,{{\\an5\\pos(540,780)\\fad(400,0)\\move(540,800,540,780,150,550)}}{esc(ec['brand'])}")
        ev.append(f"Dialogue: 6,{ts(t0 + 0.3)},{ts(total)},Shape,,0,0,0,,{{\\an7\\pos(0,0)\\1c{acc_c}\\1a&H00&\\fad(400,0)\\p1}}m 490 852 l 590 852 l 590 856 l 490 856{{\\p0}}")
        ev.append(f"Dialogue: 6,{ts(t0 + 0.3)},{ts(total)},CardSub,,0,0,0,,{{\\an5\\pos(540,905)\\fad(400,0)}}{esc(ec['sub'])}")
        cta_line = next((s.get("overlay") for s in reversed(sents) if s.get("caption_style") == "cta" and s.get("overlay")), "") \
            or "Contact us right now"
        pill_w = min(W - 2 * side, 60 + 26 * len(cta_line))
        px0, px1 = (W - pill_w) // 2, (W + pill_w) // 2
        ev.append(f"Dialogue: 6,{ts(t0 + 0.5)},{ts(total)},Shape,,0,0,0,,{{\\an7\\pos(0,0)\\1c{ass_color(pal['panel'])}\\1a&H00&\\fad(300,0)\\p1}}{rounded_rect(px0, 975, px1, 1075, 50)}{{\\p0}}")
        ev.append(f"Dialogue: 7,{ts(t0 + 0.5)},{ts(total)},CardCta,,0,0,0,,{{\\an5\\pos(540,1025)\\fad(300,0)}}{esc(cta_line.replace('*', ''))}")
        if ec.get("contact"):
            ev.append(f"Dialogue: 6,{ts(t0 + 0.7)},{ts(total)},CardSub,,0,0,0,,{{\\an5\\pos(540,1140)\\fad(300,0)\\c{acc_c}}}{esc(ec['contact'])}")
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    run = Path(a.run_dir)
    tl = fit(cfg, read_json(run / "script.json"), read_json(run / "audio_meta.json"),
             read_json(cfg["_paths"]["catalog_file"]), run)
    print(json.dumps({"scenes": len(tl["timeline"]), "seconds": tl["total_duration_seconds"]}))

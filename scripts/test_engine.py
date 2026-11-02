#!/usr/bin/env python3
"""End-to-end engine test against the synthetic song with known timings."""
import json
import os
import re
import sys

os.environ["STS_AUTOLAUNCH"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import timestamp_studio as sts  # noqa: E402

SONG = os.path.join(HERE, "testdata", "test_song.wav")
TRUTH = json.load(open(os.path.join(HERE, "testdata", "ground_truth.json")))
LYRICS = sts.EXAMPLE_LYRICS

failures = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        failures.append(name)


def main():
    print("=== 0 · formatter edge cases ===")
    check("fmt_clock 59.9996 -> 01:00.000", sts.fmt_clock(59.9996) == "01:00.000", sts.fmt_clock(59.9996))
    check("fmt_clock srt hours", sts.fmt_clock(6.0, comma=True, force_hours=True) == "00:00:06,000",
          sts.fmt_clock(6.0, comma=True, force_hours=True))
    check("fmt_lrc_stamp 59.996 -> [01:00.00]", sts.fmt_lrc_stamp(59.996) == "[01:00.00]", sts.fmt_lrc_stamp(59.996))
    check("fmt_yt 3599.999 -> 1:00:00", sts.fmt_yt(3599.999) == "1:00:00", sts.fmt_yt(3599.999))
    check("csv field escapes quotes", sts._csv_field('say "hi"') == '"say ""hi"""', sts._csv_field('say "hi"'))

    print("\n=== 1 · forced-alignment accuracy (model=base, lang=en) ===")
    res = sts.run_alignment(SONG, LYRICS, model_size="base", language="en", isolate_vocals_flag=False)
    print("STATUS:", res["status"].replace("\n", " | ")[:400])
    sing = [e for e in res["entries"] if e["kind"] == "sing"]
    tags = [e for e in res["entries"] if e["kind"] == "tag"]
    check("9 entries parsed (6 sing + 3 tags)", len(sing) + len(tags) == 9, f"{len(sing)} sing + {len(tags)} tags")
    check("6 sing lines", len(sing) == 6, f"got {len(sing)}")
    check("match rate reported", res["match_rate"] is not None and res["match_rate"] > 0.5, f"{res['match_rate']}")

    print("\nline-by-line error vs ground truth:")
    errs = []
    for e, gt in zip(sing, TRUTH["lines"]):
        err = e["start"] - gt["start"]
        errs.append(err)
        print(f"  {e['text'][:44]:46s} pred {e['start']:7.2f}  true {gt['start']:7.2f}  err {err:+.2f}s")
    max_err = max(abs(e) for e in errs)
    mean_err = sum(errs) / len(errs)
    print(f"  max |err| = {max_err:.2f}s   mean err = {mean_err:+.2f}s")
    check("all 6 lines within ±1.0 s", max_err <= 1.0, f"max {max_err:.2f}s")

    print("\n=== 2 · chapters (from [Intro]/[Verse 1]/[Chorus] tags) ===")
    chs = res["chapters"]
    names = [c["name"] for c in chs]
    print("\n  chapters:", [c['name'] for c in chs], "| note:", res["chapter_note"])
    check("chapters exist", len(chs) >= 3, str(len(chs)))
    check("chapter 1 starts ~0", abs(chs[0]["start"]) < 0.6, f"{chs[0]['start']:.2f}")
    check("Chorus present", "Chorus" in names)

    print("\n=== 3 · beats + cut plan ===")
    print(f"  bpm={res['bpm']} beats={len(res['beats'])}")
    check("bpm detected near 100", res["bpm"] and 85 <= res["bpm"] <= 115, f"{res['bpm']}")
    check("beats found", len(res["beats"]) >= 60, str(len(res["beats"])))
    cp = res["cut_plan"]
    print(f"  cut plan rows: {len(cp)}; first: {cp[0] if cp else None}")
    check("cut plan rows exist", len(cp) >= 8, str(len(cp)))
    durs = [r["duration"] for r in cp]
    check("clip durations ≈ 4 beats (2.4 s @100bpm, boundary slots may stretch)", all(2.0 <= d <= 3.6 for d in durs), f"{durs[:4]}…")
    check("frames = duration*24", all(r["frames"] == round(r["duration"] * 24) for r in cp))

    print("\n=== 4 · output formats ===")
    outs = sts.render_outputs(res, 0.0)
    for key in ["lrc", "srt", "vtt", "chapters", "reaper", "cutplan", "beats", "json"]:
        val = outs[key]
        check(f"{key} non-empty", bool(val.strip()), f"{len(val)} chars")
    check("lrc has stamps", outs["lrc"].count("[00:") + outs["lrc"].count("[01:") >= 8)
    check("srt block count == 6", outs["srt"].strip().split("\n\n").__len__() == 6)
    srt_stamps = [ln for ln in outs["srt"].splitlines() if "-->" in ln]
    srt_ok = bool(srt_stamps) and all(re.fullmatch(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", s) for s in srt_stamps)
    check("srt stamps strict H:MM:SS,mmm", srt_ok, srt_stamps[0] if srt_stamps else "none")
    check("vtt header", outs["vtt"].startswith("WEBVTT"))
    check("reaper csv header", outs["reaper"].startswith("#,Name,Start,End,Length,Color"))
    check("reaper has markers+regions", "M1," in outs["reaper"] and "R1," in outs["reaper"])
    reaper_rows = [ln for ln in outs["reaper"].splitlines()[1:] if ln.strip()]
    check("reaper rows all 6 fields", all(len(ln.split(",")) >= 5 and ln.split(",")[2].count(":") == 2 for ln in reaper_rows),
          reaper_rows[0] if reaper_rows else "none")
    check("cutplan header", outs["cutplan"].startswith("clip,section,start,end,duration_seconds,frames_at_24fps"))
    prev_rows = outs["preview"]
    check("preview rows have 5 columns", all(len(r) == 5 for r in prev_rows), str(prev_rows[0]) if prev_rows else "none")
    conf_cells = [r[4] for r in prev_rows if r[0] and "section" not in str(r[4])]
    check("preview confidence present", bool(conf_cells) and all("%" in c or c == "auto" for c in conf_cells), str(conf_cells))

    zpath = sts.build_zip(res, 0.0)
    import zipfile

    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
    print("  zip contents:", names)
    check("zip has 9 files", len(names) == 9, str(len(names)))

    print("\n=== 5 · nudge offset +3.2s ===")
    outs2 = sts.render_outputs(res, 3.2)
    first_lrc = outs2["lrc"].splitlines()[0]
    print("  lrc line 1 shifted:", first_lrc)
    check("offset applied", first_lrc.startswith("[00:0") or first_lrc.startswith("[00:1"))

    print("\n=== 6 · auto-transcribe mode (no lyrics) ===")
    res2 = sts.run_alignment(SONG, "", model_size="tiny", language="en", isolate_vocals_flag=False)
    sing2 = [e for e in res2["entries"] if e["kind"] == "sing"]
    print(f"  transcribed {len(sing2)} lines; status: {res2['status'][:120]}")
    check("auto mode produced lines", len(sing2) >= 4, str(len(sing2)))

    print("\n=== SUMMARY ===")
    if failures:
        print(f"❌ {len(failures)} failure(s): {failures}")
        sys.exit(1)
    print("✅ all checks passed")


if __name__ == "__main__":
    main()

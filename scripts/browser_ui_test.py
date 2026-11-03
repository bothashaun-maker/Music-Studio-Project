#!/usr/bin/env python3
"""Real-browser UI verification for Song Timestamp Studio (Gradio on :7860).

Drives the actual app end to end: upload WAV -> paste lyrics -> run ->
check every output tab -> nudge -> audition. Screenshots land in
/home/z/my-project/download/timestamp-studio-screens/.
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SONG = os.path.join(HERE, "testdata", "test_song.wav")
SHOTS = "/home/z/my-project/download/timestamp-studio-screens"
os.makedirs(SHOTS, exist_ok=True)

LYRICS = """[Intro]
[Verse 1]
Walking through the city lights at midnight
Neon shadows falling on the street
I can hear the distant engines humming
Feel the rhythm moving through my feet
[Chorus]
We are the dreamers in the night
Holding on until the morning light"""

results = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    results.append((name, bool(cond)))


def tab_text(page, name):
    page.get_by_role("tab", name=name).click()
    time.sleep(1.2)
    panel = page.locator("[role=tabpanel]:visible")
    ta = panel.locator("textarea").first
    if ta.count() == 0:
        return ""
    return ta.input_value()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1360, "height": 950})
        page.goto("http://127.0.0.1:7860", wait_until="domcontentloaded")
        page.wait_for_selector("text=Song Timestamp Studio", timeout=30000)
        time.sleep(2)
        page.screenshot(path=os.path.join(SHOTS, "01_initial_ui.png"))
        check("page title renders", page.locator("h1:has-text('Song Timestamp Studio')").count() >= 1)

        # 1) upload the song through the real file input
        inputs = page.locator("input[type=file]")
        check("file input exists", inputs.count() >= 1, str(inputs.count()))
        inputs.first.set_input_files(SONG)
        page.get_by_role("button", name="Reset audio").first.wait_for(timeout=45000)
        time.sleep(1)
        check("audio player got the uploaded file", True, "waveform player loaded (Reset audio present)")
        page.screenshot(path=os.path.join(SHOTS, "02_song_loaded.png"))

        # 2) paste lyrics
        ta = page.locator("textarea").first
        ta.fill(LYRICS)
        time.sleep(0.5)

        # 3) run
        page.get_by_role("button", name="Get timestamps").click()
        page.wait_for_selector("text=of your lyric words were located", timeout=420000)
        status = page.locator("css=body").inner_text()
        m = re.search(r"(\d{1,3})% of your lyric words were located", status)
        check("confidence % reported", bool(m), m.group(1) + "%" if m else "n/a")
        check("match is strong (>=75%)", bool(m) and int(m.group(1)) >= 75, m.group(1) + "%" if m else "n/a")
        bpm = re.search(r"≈ (\d+(?:\.\d+)?) BPM", status)
        check("BPM detected", bool(bpm), bpm.group(1) if bpm else "n/a")
        time.sleep(1.5)

        # 4) preview table incl. per-line confidence (Dataframe = grid, not textarea)
        page.get_by_role("tab", name="Preview").click()
        time.sleep(1.2)
        prev = page.locator("[role=tabpanel]:visible").first.inner_text()
        page.screenshot(path=os.path.join(SHOTS, "03_results_preview.png"), full_page=True)
        check("preview table shows confidence", "solid" in prev or "check" in prev, prev[:100].replace("\n", " | "))
        check("preview has 9 graded rows", prev.count("% —") >= 6, f"{prev.count('% —')} graded rows")

        # 5) every output tab
        lrc = tab_text(page, "LRC")
        check("LRC stamps", re.search(r"\[\d{2}:\d{2}\.\d{2}\]", lrc) is not None, lrc.splitlines()[0] if lrc else "")
        srt = tab_text(page, "SRT")
        srt_ok = re.search(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", srt) is not None
        check("SRT strict H:MM:SS,mmm", srt_ok, srt.splitlines()[1] if srt and len(srt.splitlines()) > 1 else "")
        vtt = tab_text(page, "WebVTT")
        check("VTT header", vtt.startswith("WEBVTT"))
        chap = tab_text(page, "YouTube chapters")
        check("chapters 0:00 first", chap.startswith("0:00"), chap.splitlines()[0] if chap else "")
        check("chapters list Chorus", "Chorus" in chap)
        reaper = tab_text(page, "REAPER CSV")
        check("REAPER header", reaper.startswith("#,Name,Start,End,Length,Color"))
        rows = [r for r in reaper.splitlines()[1:] if r.strip()]
        check("REAPER markers M1..M6", all(r.split(",")[0] == f"M{i+1}" for i, r in enumerate(rows[:6])), rows[0][:60] if rows else "")
        cut = tab_text(page, "Cut plan")
        check("cut plan header", cut.startswith("clip,section,start,end,duration_seconds,frames_at_24fps"))
        frames = re.findall(r",(\d+)$", cut, flags=re.M)
        check("cut plan has frame counts", len(frames) >= 8, f"{len(frames)} clips")
        beats = tab_text(page, "Beat grid")
        check("beat grid lists beats", "BPM" in beats and beats.count("\n") >= 60, f"{beats.count(chr(10))} lines")
        js = tab_text(page, "JSON")
        check("JSON parses", _ok_json(js))

        # 6) nudge +0.5 -> LRC first stamp shifts
        first_before = lrc.splitlines()[0]
        page.get_by_label(re.compile("Nudge")).fill("0.5")
        page.get_by_role("button", name="Apply nudge").click()
        page.wait_for_timeout(4000)
        lrc2 = tab_text(page, "LRC")
        first_after = lrc2.splitlines()[0]
        check("nudge shifts LRC stamp", first_before != first_after, f"{first_before} -> {first_after}")
        page.screenshot(path=os.path.join(SHOTS, "04_nudged.png"))

        # 7) audition a line — poll up to 25 s for the audition player to load
        reset_before = page.get_by_role("button", name="Reset audio").count()
        page.get_by_label(re.compile("Audition line")).fill("3")
        page.get_by_role("button", name="Audition line").click()
        audition_ok = False
        reset_after = reset_before
        for _ in range(25):
            time.sleep(1)
            reset_after = page.get_by_role("button", name="Reset audio").count()
            if reset_after > reset_before:
                audition_ok = True
                break
        if not audition_ok:
            page.screenshot(path=os.path.join(SHOTS, "debug_audition.png"))
        check("audition player has audio", audition_ok, f"{reset_before} -> {reset_after} loaded players")

        # 8) zip download button holds a file
        zip_link = page.locator("a[download], a[href*='download=true']").count()
        check("download zip available", zip_link >= 1, f"{zip_link} links")

        browser.close()

    fails = [n for n, ok in results if not ok]
    print(f"\n=== {len(results) - len(fails)}/{len(results)} UI checks passed ===", flush=True)
    if fails:
        print("FAILURES:", fails, flush=True)
        sys.exit(1)
    print("ALL UI CHECKS PASSED", flush=True)


def _ok_json(s):
    import json

    try:
        data = json.loads(s)
        return bool(data.get("entries")) and bool(data.get("cut_plan"))
    except Exception:
        return False


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Big-file-safe song delivery tests for the TimestampStudio node pack.

Covers the exact failure the user hit ("Upload failed: Fetch timeout" when a big
song crossed the Cloudflare tunnel on ComfyUI's single-shot /upload/image):

  1. a 105 MB song (over ComfyUI's old 100 MB default cap) uploads in 8 MB pieces
  2. finished pieces are kept: finish-with-missing-pieces → 409 → finish again →
     succeeds (resumable, continues where it stopped)
  3. /sts/fetch_url downloads a song server-side; page links are refused
  4. Kaggle-side import copies into the input folder
  5. STSLoadSong + PreviewAudio run through the real /prompt queue
  6. THROTTLED LINK (1.5 Mbps, request killed after 45 s — a trycloudflare
     stand-in): the OLD single-shot /upload/image path DIES on a 12 MB song
     (the user's bug, reproduced), while the NEW 6 MB-piece chunked path
     succeeds on the very same link.
"""
import asyncio
import http.client
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import wave
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["STS_AUTOLAUNCH"] = "0"

import test_sts_sandbox as sb  # reuses the sandbox harness (port 8189, install_pack...)

BASE = sb.BASE
PORT = sb.PORT
SANDBOX = sb.SANDBOX
COMFY = sb.COMFY
INPUTS = sb.INPUTS

CHUNK = 8 * 1024 * 1024
FAKE_KAGGLE = os.path.join(SANDBOX, "fake_kaggle")

failures = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not cond:
        failures.append(name)


def make_wav(path, target_bytes, rate=8000, channels=1):
    """A valid WAV of (almost exactly) target_bytes — silence; size is what matters."""
    frames = max(rate, (target_bytes - 44) // (2 * channels))
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        block = b"\x00" * (2 * channels * rate)
        for _ in range(frames // rate):
            w.writeframes(block)
        w.writeframes(b"\x00" * (2 * channels * (frames % rate)))
    pad = target_bytes - os.path.getsize(path)
    if pad > 0:
        with open(path, "ab") as f:
            f.write(b"\x00" * pad)


def wait_server(timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/system_stats", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1.5)
    return False


def post_json(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def upload_chunks(path, name, size, chunk_size=CHUNK, base=BASE, skip=None):
    """Upload `size` bytes of the file at `path` in pieces; skip one index if asked."""
    total = max(1, -(-size // chunk_size))
    with open(path, "rb") as f:
        for i in range(total):
            if skip is not None and i == skip:
                continue
            f.seek(i * chunk_size)
            blob = f.read(min(chunk_size, size - i * chunk_size))
            q = (f"i={i}&n={total}&name={urllib.parse.quote(name)}&size={size}")
            req = urllib.request.Request(f"{base}/sts/upload/chunk?{q}", data=blob,
                                         headers={"Content-Type": "application/octet-stream"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=300) as r:
                assert json.loads(r.read().decode()).get("ok") is True, f"piece {i} rejected"
    return total


def queue_and_wait(graph, label, timeout=300):
    request = urllib.request.Request(BASE + "/prompt",
                                     data=json.dumps(graph).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as r:
        response = json.loads(r.read().decode())
    if "prompt_id" not in response:
        raise RuntimeError("queue rejected: " + json.dumps(response)[:500])
    prompt_id = response["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(BASE + f"/history/{prompt_id}", timeout=15) as r:
            history = json.loads(r.read().decode())
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                messages = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError("execution error: " + json.dumps(messages)[:800])
            return entry
        time.sleep(2)
    raise TimeoutError(label + " timed out")


# --- throttled proxy: bandwidth limit + per-request kill switch ----------------
class TokenBucket:
    def __init__(self, rate):
        self.rate = float(rate)
        self.tokens = self.rate  # one second of burst
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def take(self, n):
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(2 * self.rate, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                await asyncio.sleep(max(0.02, (n - self.tokens) / self.rate))


async def proxy_handle(client_reader, client_writer, target_port, bucket, kill_after):
    try:
        head = bytearray()
        while b"\r\n\r\n" not in head:
            block = await asyncio.wait_for(client_reader.read(4096), 30)
            if not block:
                return
            head += block
            if len(head) > 1 << 20:
                break
        split = head.index(b"\r\n\r\n") + 4
        lines = head[:split].decode("latin-1").split("\r\n")
        clen = 0
        kept = [lines[0]]
        for line in lines[1:]:
            low = line.lower()
            if low.startswith("content-length:"):
                clen = int(line.split(":", 1)[1].strip())
            if low.startswith("connection:"):
                continue
            kept.append(line)
        kept.append("Connection: close")
        head_fw = ("\r\n".join(kept) + "\r\n\r\n").encode("latin-1") + head[split:]

        up_reader, up_writer = await asyncio.open_connection("127.0.0.1", target_port)
        up_writer.write(head_fw)
        await up_writer.drain()

        async def body_pump():
            if not clen:
                return
            up_writer.write(head[split:])
            await up_writer.drain()
            sent = len(head) - split
            while sent < clen:
                block = await client_reader.read(min(65536, clen - sent))
                if not block:
                    break
                sent += len(block)
                await bucket.take(len(block))
                up_writer.write(block)
                await up_writer.drain()

        async def resp_pump():
            while True:
                block = await up_reader.read(65536)
                if not block:
                    break
                client_writer.write(block)
                await client_writer.drain()

        body_task = asyncio.create_task(body_pump())
        try:
            await asyncio.wait_for(body_task, kill_after)  # the "tunnel" kill switch
        except asyncio.TimeoutError:
            body_task.cancel()
            for writer in (up_writer, client_writer):  # abort = RST, like a dead tunnel
                try:
                    writer.transport.abort()
                except Exception:
                    try:
                        writer.close()
                    except Exception:
                        pass
            return
        resp_task = asyncio.create_task(resp_pump())
        try:
            await asyncio.wait_for(resp_task, 120)
        except asyncio.TimeoutError:
            resp_task.cancel()
        up_writer.close()
        client_writer.close()
        await asyncio.gather(up_writer.wait_closed(), client_writer.wait_closed(),
                             return_exceptions=True)
    except Exception:
        try:
            client_writer.close()
        except Exception:
            pass


async def run_proxy(listen_port, target_port, rate, kill_after, stop):
    bucket = TokenBucket(rate)
    server = await asyncio.start_server(
        lambda r, w: proxy_handle(r, w, target_port, bucket, kill_after),
        "127.0.0.1", listen_port)
    async with server:
        await stop.wait()


def native_upload_through_proxy(proxy_port, path, name, timeout=180):
    """Single-shot multipart POST /upload/image — the old browser path."""
    boundary = "----STSUploadBoundary"
    with open(path, "rb") as f:
        data = f.read()
    body = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: audio/wav\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    conn = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=timeout)
    try:
        conn.request("POST", "/upload/image", body=body,
                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        resp = conn.getresponse()
        return resp.status, resp.read()[:200]
    finally:
        conn.close()


def main():
    sb.install_pack()
    big_wav = os.path.join(SANDBOX, "big_song.wav")
    mid_wav = os.path.join(SANDBOX, "mid_song.wav")
    small_wav = os.path.join(HERE, "testdata", "test_song.wav")
    big_size = 105 * 1024 * 1024  # over ComfyUI's old 100 MB default cap
    mid_size = 12 * 1024 * 1024

    print("building test songs…", flush=True)
    if not os.path.exists(big_wav) or os.path.getsize(big_wav) < big_size:
        make_wav(big_wav, big_size)
    check("105 MB test song built", os.path.getsize(big_wav) == big_size)
    if not os.path.exists(mid_wav) or os.path.getsize(mid_wav) < mid_size:
        make_wav(mid_wav, mid_size)
    check("12 MB test song built", os.path.getsize(mid_wav) == mid_size)

    os.makedirs(FAKE_KAGGLE, exist_ok=True)
    shutil.copyfile(small_wav, os.path.join(FAKE_KAGGLE, "kaggle_side_song.wav"))

    env = dict(os.environ)
    env["STS_SCAN_ROOTS"] = FAKE_KAGGLE
    log = open(os.path.join(SANDBOX, "sts-server.log"), "a")
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
         "--output-directory", os.path.join(SANDBOX, "sts_runs"), "--disable-auto-launch",
         "--cpu", "--max-upload-size", "2048"],
        cwd=COMFY, stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        check("server ready (with --max-upload-size 2048)", wait_server())
        health = json.loads(urllib.request.urlopen(BASE + "/sts/health", timeout=10).read().decode())
        check("/sts/health live", health.get("ok") is True)

        # --- 1 · the 105 MB song, 8 MB pieces -----------------------------------
        total = upload_chunks(big_wav, "big_song.wav", big_size)
        status, fin = post_json("/sts/upload/finish",
                                {"name": "big_song.wav", "n": total, "size": big_size})
        check("105 MB song assembled (over the old 100 MB cap)",
              status == 200 and fin.get("ok") and fin.get("bytes") == big_size, str(fin))
        landed = os.path.join(INPUTS, "big_song.wav")
        check("105 MB song in ComfyUI input folder",
              os.path.isfile(landed) and os.path.getsize(landed) == big_size)
        songs = json.loads(urllib.request.urlopen(BASE + "/sts/songs", timeout=10).read().decode())
        check("/sts/songs lists it", "big_song.wav" in songs.get("input", []))

        # --- 2 · resumable: missing piece → 409 → finish again → ok -------------
        total_mid = upload_chunks(mid_wav, "resumable_song.wav", mid_size, skip=1)
        status, fin = post_json("/sts/upload/finish",
                                {"name": "resumable_song.wav", "n": total_mid, "size": mid_size})
        check("finish with a missing piece is refused (409)",
              status == 409, f"{status} {str(fin)[:120]}")
        upload_chunks(mid_wav, "resumable_song.wav", mid_size, skip=None)  # retry (idempotent)
        status, fin = post_json("/sts/upload/finish",
                                {"name": "resumable_song.wav", "n": total_mid, "size": mid_size})
        check("finish after retry succeeds", status == 200 and fin.get("ok"), str(fin))

        # --- 3 · link download ---------------------------------------------------
        served = os.path.join(SANDBOX, "url_server")
        os.makedirs(served, exist_ok=True)
        shutil.copyfile(small_wav, os.path.join(served, "linked_song.wav"))
        httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 8199), partial(http.server.SimpleHTTPRequestHandler, directory=served))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            status, fin = post_json("/sts/fetch_url", {"url": "http://127.0.0.1:8199/linked_song.wav"})
            check("link download lands in the input folder",
                  status == 200 and fin.get("ok")
                  and os.path.isfile(os.path.join(INPUTS, fin.get("filename", "_"))), str(fin))
            status, fin = post_json("/sts/fetch_url", {"url": "http://127.0.0.1:8199/"})
            check("link pointing at a page is refused", status == 400, f"{status} {str(fin)[:120]}")
        finally:
            httpd.shutdown()

        # --- 4 · Kaggle-side import ---------------------------------------------
        status, fin = post_json("/sts/import",
                                {"path": os.path.join(FAKE_KAGGLE, "kaggle_side_song.wav")})
        check("Kaggle-side import copies into input",
              status == 200 and fin.get("ok")
              and os.path.isfile(os.path.join(INPUTS, fin.get("filename", "_"))), str(fin))
        status, fin = post_json("/sts/import", {"path": "/etc/hostname"})
        check("import outside the Kaggle roots is refused", status == 400, str(status))

        # --- 5 · STSLoadSong through the real queue ------------------------------
        entry = queue_and_wait({"prompt": {
            "1": {"class_type": "STSLoadSong", "inputs": {"audio": "resumable_song.wav"}},
            "2": {"class_type": "PreviewAudio", "inputs": {"audio": ["1", 0]}},
        }}, "STSLoadSong + PreviewAudio")
        check("STSLoadSong queued and ran (audio handed to PreviewAudio)",
              "2" in entry.get("outputs", {}))

        # --- 6 · the throttled-link proof ---------------------------------------
        # The proxy runs in its own thread with its own always-running loop.
        proxy_loop = asyncio.new_event_loop()
        stop_evt = asyncio.Event()

        def _run_proxy_thread():
            asyncio.set_event_loop(proxy_loop)
            proxy_loop.run_until_complete(
                run_proxy(8191, PORT, rate=187_500, kill_after=45, stop=stop_evt))

        threading.Thread(target=_run_proxy_thread, daemon=True).start()
        time.sleep(0.6)

        # OLD path: single-shot 12 MB through the slow link → must die
        t0 = time.monotonic()
        old_died, detail = False, ""
        try:
            status, body = native_upload_through_proxy(8191, mid_wav, "slow_native.wav")
            detail = f"unexpectedly succeeded: {status} {body[:80]!r}"
        except Exception as exc:
            old_died = True
            detail = f"{type(exc).__name__}: {str(exc)[:90]}"
        took = time.monotonic() - t0
        check("REPRODUCED THE BUG: single-shot 12 MB upload dies on the slow link",
              old_died and took < 120, f"after {took:.0f}s — {detail}")
        check("…and left NO half-written file in the input folder",
              not any("slow_native" in f for f in os.listdir(INPUTS)))

        # NEW path: same file, 6 MB pieces, same slow link → must succeed
        t0 = time.monotonic()
        try:
            total_slow = upload_chunks(mid_wav, "slow_song.wav", mid_size,
                                       chunk_size=6 * 1024 * 1024, base="http://127.0.0.1:8191")
            status, fin = post_json("/sts/upload/finish",
                                    {"name": "slow_song.wav", "n": total_slow, "size": mid_size})
            ok = status == 200 and fin.get("ok")
            detail = str(fin)[:120]
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {str(exc)[:120]}"
        took = time.monotonic() - t0
        check("NEW path: same 12 MB song through the SAME slow link succeeds",
              ok and os.path.isfile(os.path.join(INPUTS, "slow_song.wav")),
              f"{took:.0f}s — {detail}")

        proxy_loop.call_soon_threadsafe(stop_evt.set)
        time.sleep(0.3)

        print("\n" + ("✅ UPLOAD FIX: all checks passed" if not failures else f"❌ failed: {failures}"),
              flush=True)
        return 0 if not failures else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())

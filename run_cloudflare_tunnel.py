"""cloudflared calistirir; trycloudflare URL'sini yakalayip Telegram Mini App'e yazar."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from miniapp_url_sync import apply_miniapp_url, extract_trycloudflare_url

ROOT = Path(__file__).resolve().parent


def _cloudflared_bin() -> str:
    found = shutil.which("cloudflared")
    if not found:
        raise SystemExit(
            "cloudflared bulunamadi. Kurun: winget install Cloudflare.cloudflared"
        )
    return found


def _run(cmd: list[str], *, capture_urls: bool) -> int:
    print(" ".join(cmd), flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    seen = ""
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if not capture_urls:
                continue
            url = extract_trycloudflare_url(line)
            if not url or url == seen:
                continue
            seen = url
            try:
                apply_miniapp_url(url, push_telegram=True)
                print(f"\n[OK] Mini App URL Telegram + .env: {url}\n", flush=True)
            except Exception as exc:
                print(f"\n[HATA] Mini App URL yazilamadi ({url}): {exc}\n", flush=True)
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 130


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Yerel API, ornek http://127.0.0.1:8080")
    parser.add_argument("--token", help="CLOUDFLARE_TUNNEL_TOKEN (sabit domain)")
    args = parser.parse_args()
    bin_path = _cloudflared_bin()
    if not args.token:
        raise SystemExit(
            "Sabit adres icin Cloudflare named tunnel tokeni kullanin; "
            "gecici --url tunelleri desteklenmiyor."
        )
    return _run([bin_path, "tunnel", "run", "--token", args.token], capture_urls=False)


if __name__ == "__main__":
    raise SystemExit(main())


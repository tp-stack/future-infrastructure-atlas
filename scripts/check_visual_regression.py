"""Headless visual regression checks for Atlas map routes.

This intentionally uses only the Python standard library plus a local Chrome/
Chromium executable. It starts the Vite dev server, captures screenshots for
critical routes, decodes the PNGs, and fails when the map area is visually empty
or black.
"""

from __future__ import annotations

import argparse
import os
import signal
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "reports" / "visual_regression"


@dataclass(frozen=True)
class Crop:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class RouteCheck:
    path: str
    label: str
    crop: Crop
    min_non_dark: int
    min_signal: int


ROUTES = [
    RouteCheck(
        path="/",
        label="normal reliable map",
        crop=Crop(x=380, y=120, width=860, height=610),
        min_non_dark=2_500,
        min_signal=0,
    ),
    RouteCheck(
        path="/?reliableMap=1",
        label="clean reliable map",
        crop=Crop(x=220, y=110, width=840, height=560),
        min_non_dark=4_000,
        min_signal=400,
    ),
    RouteCheck(
        path="/?maplibreMap=1",
        label="protected maplibreMap route",
        crop=Crop(x=220, y=110, width=840, height=560),
        min_non_dark=4_000,
        min_signal=400,
    ),
    RouteCheck(
        path="/?globe=1",
        label="globe prototype route",
        crop=Crop(x=230, y=80, width=820, height=620),
        min_non_dark=3_500,
        min_signal=250,
    ),
    RouteCheck(
        path="/?globe=1&proof=1",
        label="globe proof route",
        crop=Crop(x=230, y=80, width=820, height=620),
        min_non_dark=3_500,
        min_signal=250,
    ),
    RouteCheck(
        path="/?commercialApi=1",
        label="commercial api console route",
        crop=Crop(x=80, y=80, width=1040, height=620),
        min_non_dark=12_000,
        min_signal=350,
    ),
    RouteCheck(
        path="/?commercialPanel=1",
        label="world map commercial workbench overlay",
        crop=Crop(x=390, y=75, width=760, height=560),
        min_non_dark=8_500,
        min_signal=280,
    ),
]


class VisualCheckError(RuntimeError):
    """Raised when a visual regression check fails."""


def find_executable(names: list[str]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def find_chrome() -> str | None:
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    candidates = [
        "chrome",
        "chrome.exe",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "msedge",
        "msedge.exe",
    ]
    found = find_executable(candidates)
    if found:
        return found

    windows_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in windows_paths:
        if path.exists():
            return str(path)
    return None


def find_npm() -> str | None:
    return find_executable(["npm.cmd", "npm"])


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout_seconds: float = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - surfaced after timeout
            last_error = exc
        time.sleep(0.5)
    raise VisualCheckError(f"Timed out waiting for {url}: {last_error}")


def start_vite(port: int) -> subprocess.Popen[str]:
    npm = find_npm()
    if not npm:
        raise VisualCheckError("npm is required for visual checks. Install Node/npm and run npm install in frontend/.")

    vite_bin = FRONTEND_ROOT / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if not vite_bin.exists():
        raise VisualCheckError("frontend/node_modules is missing. Run `cd frontend && npm install` before visual checks.")

    command = [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]
    return subprocess.Popen(
        command,
        cwd=FRONTEND_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=5)


def capture_screenshot(chrome: str, url: str, output_path: Path) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: str | None = None
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix="atlas-chrome-profile-") as user_data_dir:
            command = [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                f"--window-size={DEFAULT_WIDTH},{DEFAULT_HEIGHT}",
                "--hide-scrollbars",
                "--virtual-time-budget=6000",
                f"--user-data-dir={user_data_dir}",
                f"--screenshot={output_path}",
                url,
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=75)
            except subprocess.TimeoutExpired:
                last_error = f"Chrome screenshot timed out for {url} on attempt {attempt + 1}"
                continue
        if result.returncode == 0:
            break
        last_error = (
            f"Chrome screenshot failed for {url} (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    else:
        raise VisualCheckError(last_error or f"Chrome screenshot failed for {url}")

    if result.returncode != 0:
        raise VisualCheckError(
            f"Chrome screenshot failed for {url} (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise VisualCheckError(f"Chrome did not write screenshot: {output_path}")


def paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png_rgba(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise VisualCheckError(f"Not a PNG file: {path}")

    offset = 8
    width = height = bit_depth = color_type = None
    idat_parts: list[bytes] = []
    while offset < len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        chunk_type = raw[offset + 4 : offset + 8]
        chunk_data = raw[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB",
                chunk_data,
            )
            if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
                raise VisualCheckError(f"Unsupported PNG format in {path}")
            if color_type not in {2, 6}:
                raise VisualCheckError(f"Unsupported PNG color type {color_type} in {path}")
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None:
        raise VisualCheckError(f"PNG missing IHDR: {path}")

    channels = 4 if color_type == 6 else 3
    row_bytes = width * channels
    decompressed = zlib.decompress(b"".join(idat_parts))
    rows: list[bytearray] = []
    pos = 0
    previous = bytearray(row_bytes)

    for _ in range(height):
        filter_type = decompressed[pos]
        pos += 1
        current = bytearray(decompressed[pos : pos + row_bytes])
        pos += row_bytes

        for i in range(row_bytes):
            left = current[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                current[i] = (current[i] + left) & 0xFF
            elif filter_type == 2:
                current[i] = (current[i] + up) & 0xFF
            elif filter_type == 3:
                current[i] = (current[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                current[i] = (current[i] + paeth_predictor(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise VisualCheckError(f"Unsupported PNG filter {filter_type} in {path}")

        rows.append(current)
        previous = current

    rgba = bytearray(width * height * 4)
    out = 0
    for row in rows:
        for i in range(0, len(row), channels):
            rgba[out] = row[i]
            rgba[out + 1] = row[i + 1]
            rgba[out + 2] = row[i + 2]
            rgba[out + 3] = row[i + 3] if channels == 4 else 255
            out += 4

    return width, height, bytes(rgba)


def analyze_pixels(path: Path, crop: Crop) -> dict[str, int]:
    width, height, rgba = decode_png_rgba(path)
    x0 = max(0, min(width - 1, crop.x))
    y0 = max(0, min(height - 1, crop.y))
    x1 = max(x0 + 1, min(width, crop.x + crop.width))
    y1 = max(y0 + 1, min(height, crop.y + crop.height))

    counts = {
        "sampled": 0,
        "non_dark": 0,
        "amber": 0,
        "cyan": 0,
        "bright": 0,
        "red": 0,
        "signal": 0,
    }

    stride = 4
    for y in range(y0, y1, stride):
        for x in range(x0, x1, stride):
            index = (y * width + x) * 4
            r, g, b, a = rgba[index], rgba[index + 1], rgba[index + 2], rgba[index + 3]
            if a < 10:
                continue
            counts["sampled"] += 1
            if not (r < 16 and g < 20 and b < 30):
                counts["non_dark"] += 1
            if r > 170 and 90 < g < 235 and b < 120:
                counts["amber"] += 1
            if r < 130 and g > 130 and b > 145:
                counts["cyan"] += 1
            if r > 205 and g > 205 and b > 205:
                counts["bright"] += 1
            if r > 180 and g < 95 and b < 95:
                counts["red"] += 1

    counts["signal"] = counts["amber"] + counts["cyan"] + counts["bright"] + counts["red"]
    return counts


def run_visual_checks(base_url: str, output_dir: Path, keep_screenshots: bool) -> int:
    chrome = find_chrome()
    if not chrome:
        raise VisualCheckError("Chrome/Chromium is required for visual checks. Set CHROME_PATH if it is not on PATH.")

    output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    for route in ROUTES:
        filename = route.path.strip("/").replace("?", "_").replace("&", "_").replace("=", "-") or "root"
        screenshot_path = output_dir / f"{filename}.png"
        url = f"{base_url.rstrip('/')}{route.path}"
        capture_screenshot(chrome, url, screenshot_path)
        stats = analyze_pixels(screenshot_path, route.crop)
        ok = stats["non_dark"] >= route.min_non_dark and stats["signal"] >= route.min_signal
        status = "OK" if ok else "FAIL"
        print(
            f"{status}: {route.label} {route.path} "
            f"non_dark={stats['non_dark']} signal={stats['signal']} "
            f"amber={stats['amber']} cyan={stats['cyan']} bright={stats['bright']} red={stats['red']} "
            f"screenshot={screenshot_path}"
        )
        if not ok:
            failures += 1
        elif not keep_screenshots:
            screenshot_path.unlink(missing_ok=True)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Atlas visual regression checks")
    parser.add_argument("--base-url", default=os.environ.get("ATLAS_VISUAL_BASE_URL"), help="Existing app URL to test")
    parser.add_argument("--port", type=int, default=0, help="Local Vite port when --base-url is omitted")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for screenshots")
    parser.add_argument("--keep-screenshots", action="store_true", help="Keep screenshots even when checks pass")
    args = parser.parse_args()

    server: subprocess.Popen[str] | None = None
    try:
        if args.base_url:
            base_url = args.base_url
        else:
            port = args.port or find_free_port()
            server = start_vite(port)
            base_url = f"http://127.0.0.1:{port}"
            wait_for_http(base_url)

        failures = run_visual_checks(base_url, args.output_dir, args.keep_screenshots)
        if failures:
            print(f"Visual regression checks failed: {failures}", file=sys.stderr)
            return 1
        print("Visual regression checks passed.")
        return 0
    finally:
        if server:
            stop_process_tree(server)


if __name__ == "__main__":
    raise SystemExit(main())

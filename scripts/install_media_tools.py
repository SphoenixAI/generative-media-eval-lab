"""Optional workspace-local Apple Silicon tool bootstrap; no global installation."""
import hashlib
import json
from pathlib import Path
import platform
import urllib.request
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "ffmpeg": ("https://www.osxexperts.net/ffmpeg9arm.zip", "591260c945d0eef150e3bf82b0ef988bd36a9cecc18ff05d6679617159f0a95e"),
    "ffprobe": ("https://www.osxexperts.net/ffprobe9arm.zip", "e11c17e8200b3ee4c4c186d245e2b4053f01d56957336c1817fca0b997469106"),
}

if __name__ == "__main__":
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("Use system ffmpeg/ffprobe or EVAL_LAB_FFMPEG/EVAL_LAB_FFPROBE on this platform.")
    destination = ROOT / ".tools"
    destination.mkdir(exist_ok=True)
    records = []
    for name, (url, expected) in SOURCES.items():
        target = destination / name
        if target.exists():
            content = target.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read(200_000_001)
            if len(data) > 200_000_000:
                raise SystemExit("Tool archive exceeds size limit")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = [m for m in archive.infolist() if Path(m.filename).name == name and not m.filename.startswith("__MACOSX/")]
                if len(members) != 1 or members[0].file_size > 200_000_000:
                    raise SystemExit("Unexpected archive layout")
                content = archive.read(members[0])
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise SystemExit(f"{name}: publisher checksum mismatch; no executable installed")
        if not target.exists():
            target.write_bytes(content)
        target.chmod(0o755)
        records.append({"name": name, "url": url, "sha256": actual, "publisher": "OSXExperts (third-party static build)", "checksum_source": "https://www.osxexperts.net/"})
    (destination / "installation.json").write_text(json.dumps(records, indent=2)+"\n")
    print(json.dumps(records, indent=2))

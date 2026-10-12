"""Download Cricsheet's all-matches JSON zip once and extract it. Never re-downloads."""
import urllib.request
import zipfile
from pathlib import Path

URL = "https://cricsheet.org/downloads/all_json.zip"


def ensure_data(data_dir):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    zip_path = data_dir / "all_json.zip"
    raw_dir = data_dir / "raw"
    if zip_path.exists():
        print(f"[download] using cached {zip_path}")
    else:
        print(f"[download] fetching {URL}")
        tmp = zip_path.with_suffix(".part")
        urllib.request.urlretrieve(URL, tmp)
        tmp.rename(zip_path)
    if not raw_dir.exists() or not any(raw_dir.glob("*.json")):
        print(f"[download] extracting to {raw_dir}")
        raw_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                # only flat *.json members; ignore anything with a path component
                if name.endswith(".json") and "/" not in name and "\\" not in name:
                    z.extract(name, raw_dir)
    return raw_dir

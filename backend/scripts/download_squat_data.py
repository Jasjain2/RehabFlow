"""Download and extract the Zenodo squat posture dataset (DOI 10.5281/zenodo.18859797).

Each zip is verified against its published MD5. 02_Err_GoodMorning.zip also contains
copies of the other two classes, so each class folder is extracted only from its own zip.

Usage: python scripts/download_squat_data.py
"""
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BACKEND_DIR / "data" / "raw" / "squat"
ZIP_DIR = RAW_DIR / "zips"
RECORD_URL = "https://zenodo.org/api/records/18859797/files/{name}/content"

# zip name -> (published md5, class folder to extract from it)
FILES = {
    "00_Standard.zip": ("7d7c2c037139fbdbd58121f8cf17742d", "00_Standard"),
    "01_Err_Shallow.zip": ("9bffec67df8ae2f8f3e6b1eb5cb2c63c", "01_Err_Shallow"),
    "02_Err_GoodMorning.zip": ("9f0d0c36cfd8b849f04f6fbb0899e9f8", "02_Err_GoodMorning"),
}


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, expected_md5: str) -> Path:
    path = ZIP_DIR / name
    if path.exists() and md5(path) == expected_md5:
        print(f"{name}: already downloaded")
        return path
    print(f"{name}: downloading")
    urllib.request.urlretrieve(RECORD_URL.format(name=name), path)
    if md5(path) != expected_md5:
        sys.exit(f"{name}: checksum mismatch, refusing to extract")
    return path


def extract(zip_path: Path, folder: str) -> int:
    with zipfile.ZipFile(zip_path) as archive:
        members = [m for m in archive.namelist() if m.startswith(f"{folder}/") and m.endswith(".csv")]
        for member in members:
            # Guard against path traversal in archive member names
            target = (RAW_DIR / member).resolve()
            if RAW_DIR.resolve() not in target.parents:
                sys.exit(f"Unsafe path in archive: {member}")
            archive.extract(member, RAW_DIR)
    return len(members)


def main() -> None:
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    for name, (expected_md5, folder) in FILES.items():
        count = extract(download(name, expected_md5), folder)
        print(f"{name}: extracted {count} CSVs to {folder}/")


if __name__ == "__main__":
    main()

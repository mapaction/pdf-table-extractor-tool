"""
Download every document whose numeric ID is in the range specified from
https://ehtools.org and store them in ./ehtools_data_raw/.

Safe to run repeatedly  existing files are skipped.
"""

import re
import sys
import time
from pathlib import Path

import requests

# BASE_URL   = "https://ehtools.org"
# START_ID   = 1265
# END_ID     = 1299          # inclusive
# # END_ID     = 1399          # inclusive
# PDF_FOLDER = Path("ehtools_data_raw")
# PDF_FOLDER.mkdir(exist_ok=True)

# HTTP_TIMEOUT   = 60        # seconds
# POLITENESS_SEC = 0.5       # delay between requests
# USER_AGENT     = "Mozilla/5.0 (Automated PDF grabber for ehtools)"


# SESSION = requests.Session()
# SESSION.headers.update({"User-Agent": USER_AGENT})


def download_pdf(doc_id: int, PDF_FOLDER, BASE_URL, SESSION, HTTP_TIMEOUT) -> None:
    """Save one PDF to disk, skipping if it already exists."""
    target = PDF_FOLDER / f"{doc_id}.pdf"
    if target.exists():
        return

    # Primary guess
    pdf_url = f"{BASE_URL}/uploads/brochures/{doc_id}.pdf"
    r = SESSION.get(pdf_url, stream=True, timeout=HTTP_TIMEOUT)

    # Fallback: parse /view-document/<id> for an <a href="...pdf">
    if r.status_code != 200 or "pdf" not in r.headers.get("content-type", ""):
        view_html = SESSION.get(f"{BASE_URL}/view-document/{doc_id}",
                                timeout=HTTP_TIMEOUT).text
        m = re.search(r'href="(/uploads/[^"]+\.pdf)"', view_html, re.I)
        if not m:
            print(f"[{doc_id}] no PDF link found; skipping")
            return
        pdf_url = BASE_URL + m.group(1)
        r = SESSION.get(pdf_url, stream=True, timeout=HTTP_TIMEOUT)
        r.raise_for_status()

    # Stream to disk
    with open(target, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_kb = target.stat().st_size / 1024
    print(f"[{doc_id}] saved ({size_kb:.1f} KB)")


# for doc_id in range(START_ID, END_ID + 1):
#     try:
#         download_pdf(doc_id)
#         time.sleep(POLITENESS_SEC)  # respect the server
#     except Exception as exc:
#         print(f"[{doc_id}] error: {exc}", file=sys.stderr)

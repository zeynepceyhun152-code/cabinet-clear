"""
check_links.py - check that every "learn more" link still opens.

Run from the backend folder (needs internet; `requests` is already in your requirements):
    python3 check_links.py

Results:
  OK       the page opened (status 200)
  CHECK    the site refused an automatic check (403/429/999). Open the link in your browser to be sure.
  BROKEN   the page is gone or the site is down. Fix or remove that link in resources.py.
"""
import sys

import requests

from resources import all_links

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CabinetClearLinkCheck/1.0)"}


def main():
    broken = 0
    for link in all_links():
        try:
            r = requests.get(link["url"], headers=HEADERS, timeout=15, allow_redirects=True)
            code = r.status_code
        except Exception as e:
            code, r = None, None
            err = str(e)[:60]
        if code == 200:
            status = "OK"
        elif code in (403, 429, 999):
            status = "CHECK"
        else:
            status = "BROKEN"
            broken += 1
        extra = f" -> {r.url}" if r is not None and r.url != link["url"] and code == 200 else ""
        print(f"{status:7s} {code if code else 'error':>5}  {link['org'][:34]:34s} {link['title'][:44]}{extra}")
        if code is None:
            print(f"        {err}")
    print(f"\n{broken} broken link(s)." if broken else "\nNo broken links.")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()

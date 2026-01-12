import re
import hashlib
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
import requests

BASE_URL = "https://havarikommisjonen.no"
OUTFILE = "sht-fiske.xml"

INCLUDE_IF_ITEM2_CONTAINS = [
    "Fiske-/ fangstfartøy",
]

def parse_dotnet_date(s):
    m = re.search(r"Date\((\d+)\)", s or "")
    if not m:
        return None
    ms = int(m.group(1))
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

def guid_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def fetch_all_reports():
    page = 1
    all_rows = []

    while True:
        url = (
            "https://havarikommisjonen.no/partials/SearchAdvanced/MarineSimpleSearch"
            f"?sortby=name&sortorder=desc&page={page}&lcid=1044"
        )
        r = requests.get(url, timeout=30, headers={"User-Agent": "sirkel-vs.no RSS builder"})
        r.raise_for_status()

        payload = r.json()
        rows = payload.get("Reports", [])
        if not rows:
            break

        all_rows.extend(rows)
        print(f"Hentet side {page} ({len(rows)} rader)")
        page += 1

    return all_rows

def main():
    rows = fetch_all_reports()
    print("Totalt rapporter hentet:", len(rows))

    now = format_datetime(datetime.now(timezone.utc))
    items_xml = []

    for row in rows:
        item2 = (row.get("Item2") or "").strip()
        if not any(k in item2 for k in INCLUDE_IF_ITEM2_CONTAINS):
            continue

        title = (row.get("Item1") or "").strip()
        vessel_name = (row.get("Item4") or "").strip()
        report_no = (row.get("Name") or "").strip()
        rel_url = (row.get("Url") or "").strip()
        link = urljoin(BASE_URL, rel_url) if rel_url else (BASE_URL + "/Sjoefart/Avgitte-rapporter")

        dt = parse_dotnet_date(row.get("IncidentDate") or "")
        pub_date = format_datetime(dt) if dt else now

        rss_title = title

        desc = f"Type fartøy: {item2}"
        if vessel_name:
            desc += f" | Fartøy: {vessel_name}"
        if report_no:
            desc += f" | Rapport: {report_no}"

        guid = guid_for(link + "|" + report_no)

        items_xml.append(f"""    <item>
      <title><![CDATA[{rss_title}]]></title>
      <link>{link}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{desc}]]></description>
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>SHT sjøfart – fiskefartøy</title>
    <link>{BASE_URL}/Sjoefart/Avgitte-rapporter</link>
    <description>Alle SHT-rapporter filtrert på fiskefartøy</description>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""

    with open(OUTFILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"OK: Skrev {OUTFILE} med {len(items_xml)} items.")

if __name__ == "__main__":
    main()


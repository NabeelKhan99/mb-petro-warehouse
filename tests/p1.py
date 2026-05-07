#!/usr/bin/env python3
"""
UWI Key List PDF to JSON Extractor (v3 - calibrated from debug output)
========================================================================
Column boundaries calibrated from actual PDF word positions.

Usage:
    pip install pdfplumber
    python uwi_pdf_to_json.py --input "UWI Key List.pdf" --output uwi_data.json
"""

import pdfplumber
import json
import re
import argparse
from pathlib import Path

# Column boundaries derived from debug output (midpoints between columns):
#   Licence   x0=38   | Location x0=95   | W1 is at 135, Well Name at 157
#   UWI       x0=396  | Company  x0=481  | Field x0=573 | Pool x0=601
#   Unit      x0=625  | Multi    x0=656  | Status x0=695 | Status Date x0=766
#   UWI Status x0=844 | UWI Date x0=920
#
# Boundaries = midpoint between adjacent column starts:
#   Licence:      0  → 84
#   Location:    84  → 153   (mid between 95 and 157, but W1 is part of Location at 135)
#   Well Name:  153  → 390
#   UWI:        390  → 478
#   Company:    478  → 568
#   Field:      568  → 596
#   Pool:       596  → 620
#   Unit:       620  → 646
#   Multi:      646  → 680
#   Status:     680  → 750
#   Status Date:750  → 828
#   UWI Status: 828  → 908
#   UWI Date:   908  → 9999

COL_BOUNDS = [
    ("licence",      "Licence",       0,    84),
    ("location",     "Location",     84,   153),
    ("well_name",    "Well Name",   153,   390),
    ("uwi",          "UWI",         390,   478),
    ("company",      "Company",     478,   568),
    ("field",        "Field",       568,   596),
    ("pool",         "Pool",        596,   620),
    ("unit",         "Unit",        620,   646),
    ("multi",        "Multi",       646,   680),
    ("status",       "Status",      680,   750),
    ("status_date",  "Status Date", 750,   828),
    ("uwi_status",   "UWI Status",  828,   908),
    ("uwi_date",     "UWI Date",    908,  9999),
]

RE_PROVINCE    = re.compile(r"^(Manitoba|Alberta|Saskatchewan|British Columbia|Ontario)$", re.IGNORECASE)
RE_REPORT_DATE = re.compile(r"Report run on[:\s]+(.+)", re.IGNORECASE)


def group_into_lines(words, y_tolerance=3):
    lines = {}
    for w in words:
        key = round(w["top"])
        matched = next((k for k in lines if abs(k - key) <= y_tolerance), None)
        if matched is not None:
            lines[matched].append(w)
        else:
            lines[key] = [w]
    return [sorted(v, key=lambda w: w["x0"]) for _, v in sorted(lines.items())]


def parse_row(line):
    record = {col_key: [] for col_key, _, _, _ in COL_BOUNDS}
    for word in line:
        mid = (word["x0"] + word["x1"]) / 2
        for col_key, _, x_start, x_end in COL_BOUNDS:
            if x_start <= mid < x_end:
                record[col_key].append(word["text"])
                break
    return {k: " ".join(v).strip() for k, v in record.items()}


def extract_metadata(words):
    meta = {"report_title": "UWI Key List", "province": "", "report_date": "", "report_type": ""}
    texts = [w["text"] for w in words]
    full  = " ".join(texts)
    for t in texts:
        if RE_PROVINCE.match(t):
            meta["province"] = t
            break
    m = RE_REPORT_DATE.search(full)
    if m:
        meta["report_date"] = m.group(1).strip()
    if "Petroleum" in texts:
        meta["report_type"] = "Petroleum"
    return meta


def extract_pdf(pdf_path, debug_page=None):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    result = {
        "report_title": "UWI Key List",
        "province": "", "report_date": "", "report_type": "Petroleum",
        "total_pages": 0, "records": [],
    }

    with pdfplumber.open(str(pdf_path)) as pdf:
        result["total_pages"] = len(pdf.pages)
        print(f"  PDF loaded: {result['total_pages']} pages")

        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num % 100 == 0 or page_num == 1:
                print(f"  Processing page {page_num}/{result['total_pages']} ...")

            words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)

            # Debug mode: dump word positions and stop
            if debug_page and page_num == debug_page:
                print(f"\n── Word positions on page {debug_page} (width={page.width:.1f}pt) ──")
                for w in words:
                    print(f"  x0={w['x0']:6.1f}  x1={w['x1']:6.1f}  top={w['top']:6.1f}  '{w['text']}'")
                return result

            if page_num == 1:
                result.update({k: v for k, v in extract_metadata(words).items() if v})

            lines = group_into_lines(words)
            for line in lines:
                # Data rows: first token is a purely numeric licence number
                if line and line[0]["text"].isdigit():
                    rec = parse_row(line)
                    rec["page"] = page_num
                    result["records"].append(rec)

    print(f"\n  Done: {len(result['records'])} records from {result['total_pages']} pages")
    return result


def main():
    parser = argparse.ArgumentParser(description="Convert UWI Key List PDF to JSON")
    parser.add_argument("--input",  "-i", required=True,           help="Path to the PDF")
    parser.add_argument("--output", "-o", default="uwi_data.json", help="Output JSON path")
    parser.add_argument("--compact", action="store_true",          help="Compact JSON output")
    parser.add_argument("--debug-page", type=int, default=None, metavar="N",
                        help="Dump word positions for page N and exit")
    args = parser.parse_args()

    print(f"\nUWI Key List PDF → JSON")
    print(f"  Input : {args.input}")

    data = extract_pdf(args.input, debug_page=args.debug_page)

    if args.debug_page:
        return

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=None if args.compact else 2, ensure_ascii=False)

    print(f"\n  Saved   : {output_path} ({output_path.stat().st_size / 1_048_576:.1f} MB)")
    print(f"  Records : {len(data['records'])}")
    print(f"  Province: {data['province']}")
    print(f"  Date    : {data['report_date']}")

    print("\n── Sample records (first 3) ──")
    for rec in data["records"][:3]:
        print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
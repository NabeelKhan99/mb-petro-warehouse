import pdfplumber
import json
import os
import re


class SpillPDFParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_data = []
        self.date_pattern = r"\d{2}-[A-Z]{3}-\d{2}"
        self.location_pattern = r"\d{2}-\d{2}-\d{2}-\d{2}"

    def _clean_numeric(self, value):
        text_val = "".join(str(value).split()).lower()

        if text_val in ["", ".", ".00", "trace", "-", "none"]:
            return 0.0

        clean_val = re.sub(r"[^\d.]", "", text_val)

        try:
            return float(clean_val) if clean_val else 0.0
        except ValueError:
            return 0.0

    def _normalize_row(self, row, page_num):
        return {
            "spill_no": row[0],
            "spill_date": row[1],
            "company": row[2],
            "source": row[3],
            "cause": row[4],
            "location_lsd": "".join(row[5].split()) if row[5] != "N/A" else "N/A",
            "oil_vol": self._clean_numeric(row[6]),
            "sw_vol": self._clean_numeric(row[7]),
            "other_vol": self._clean_numeric(row[8]),
            "recovered_vol": self._clean_numeric(row[9]),
            "total_area": self._clean_numeric(row[10]),
            "off_lease_area": self._clean_numeric(row[11]),
            "page_source": page_num + 1
        }

    def _extract_table(self, page, page_num):
        tables = page.extract_tables()
        parsed_rows = []

        if not tables:
            return parsed_rows

        for table in tables:
            for row in table:
                if not row:
                    continue

                row = [cell.strip() if cell else "N/A" for cell in row]

                if row[0] and "spill" in row[0].lower():
                    continue

                if not re.search(self.date_pattern, " ".join(row)):
                    continue

                while len(row) < 12:
                    row.append("N/A")

                parsed_rows.append(self._normalize_row(row[:12], page_num))

        return parsed_rows

    def _extract_anchor_based(self, page, page_num):
        words = [w for w in page.extract_words() if w["top"] > 160]

        rows_dict = {}
        for w in words:
            y = int(w["top"] // 3) * 3
            if y not in rows_dict:
                rows_dict[y] = []
            rows_dict[y].append(w)

        parsed_rows = []

        for y in sorted(rows_dict.keys()):
            line_words = sorted(rows_dict[y], key=lambda x: x["x0"])
            tokens = [w["text"] for w in line_words]

            if not tokens:
                continue

            line_text = " ".join(tokens)

            if not re.search(self.date_pattern, line_text):
                continue

            # Find date index
            date_idx = -1
            for i, token in enumerate(tokens):
                if re.match(self.date_pattern, token):
                    date_idx = i
                    break

            if date_idx == -1:
                continue

            spill_no = " ".join(tokens[:date_idx]) if date_idx > 0 else "N/A"
            spill_date = tokens[date_idx]

            remaining = tokens[date_idx + 1:]

            if len(remaining) < 3:
                continue

            company = remaining[0]
            source = remaining[1]
            cause = remaining[2]

            # Detect location dynamically
            location = "N/A"
            loc_idx = -1

            for i, token in enumerate(remaining):
                if re.match(self.location_pattern, token):
                    location = token
                    loc_idx = i
                    break

            if loc_idx == -1:
                numeric_tokens = remaining[3:]
            else:
                numeric_tokens = remaining[loc_idx + 1:]

            numeric_values = []

            for token in numeric_tokens:
                cleaned = re.sub(r"[^\d.]", "", token)
                if cleaned:
                    try:
                        numeric_values.append(float(cleaned))
                    except ValueError:
                        continue

            while len(numeric_values) < 6:
                numeric_values.append(0.0)

            oil = numeric_values[0]
            sw = numeric_values[1]
            other = numeric_values[2]
            recovered = numeric_values[3]
            total = numeric_values[4]
            off_lease = numeric_values[5]

            # Sanity filter
            if oil > 1_000_000:
                continue

            parsed_rows.append({
                "spill_no": spill_no if spill_no else "N/A",
                "spill_date": spill_date,
                "company": company,
                "source": source,
                "cause": cause,
                "location_lsd": location,
                "oil_vol": oil,
                "sw_vol": sw,
                "other_vol": other,
                "recovered_vol": recovered,
                "total_area": total,
                "off_lease_area": off_lease,
                "page_source": page_num + 1
            })

        return parsed_rows

    def extract(self):
        with pdfplumber.open(self.filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                table_rows = self._extract_table(page, page_num)

                if table_rows:
                    print(f"[Page {page_num + 1}] Table extraction succeeded")
                    self.raw_data.extend(table_rows)
                else:
                    print(f"[Page {page_num + 1}] Using anchor-based parsing")
                    anchor_rows = self._extract_anchor_based(page, page_num)
                    self.raw_data.extend(anchor_rows)

    def save_to_bronze(self):
        output_dir = os.path.join("data", "processed")
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, "bronze_spills.json")

        with open(output_file, "w") as f:
            json.dump(self.raw_data, f, indent=4)

        print(f"Data saved to: {output_file}")


if __name__ == "__main__":
    parser = SpillPDFParser(os.path.join("data", "raw", "spill_report.pdf"))

    parser.extract()

    if parser.raw_data:
        parser.save_to_bronze()
        print(json.dumps(parser.raw_data[0], indent=4))
import pdfplumber
import re
import json


class WellLicencePDFExtractor:

    def __init__(self, file_path):
        self.file_path = file_path

    def extract_text(self):
        text_pages = []

        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()

                if text:
                    text_pages.append(text)

        full_text = "\n".join(text_pages)

        if not full_text.strip():
            raise ValueError("No text extracted from PDF. Likely requires OCR.")

        return full_text

    def normalize_text(self, text):
        """
        Fix PDF formatting issues:
        - line breaks inside rows
        - inconsistent spacing
        """

        # Replace newlines with space
        text = text.replace("\n", " ")

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract_licence_blocks(self, text):
        """
        Split text into licence-based blocks using licence ID positions.
        This avoids issues with broken rows.
        """

        matches = list(re.finditer(r"\b\d{5}\b", text))

        indices = [m.start() for m in matches]

        blocks = []

        for i in range(len(indices)):
            start = indices[i]
            end = indices[i + 1] if i + 1 < len(indices) else len(text)

            block = text[start:end].strip()
            blocks.append(block)

        return blocks

    def parse_block(self, block):
        """
        Extract minimal structured data.
        Keep raw_block for downstream parsing in Silver layer.
        """

        licence_match = re.search(r"\b\d{5}\b", block)
        uwi_match = re.search(r"\d{3}\.\d{2}-\d{2}-\d{3}-\d{2}W1\.\d{2}", block)

        return {
            "licence_id": licence_match.group(0) if licence_match else None,
            "uwi": uwi_match.group(0) if uwi_match else None,
            "raw_block": block.strip()
        }

    def parse_metadata(self, text):
        """
        Extract report-level metadata.
        Keep raw values for later normalization in Silver layer.
        """

        title_match = re.search(r"New Well.*Approvals", text)
        date_match = re.search(r"\w+ \w+ \d{1,2}, \d{4}.*?(AM|PM)", text)

        return {
            "report_title": title_match.group(0) if title_match else "UNKNOWN",
            "report_date_raw": date_match.group(0) if date_match else None
        }

    def build_json(self):

        raw_text = self.extract_text()

        print("===== DEBUG TEXT SAMPLE =====")
        print(raw_text[:1000])
        print("===== END DEBUG =====")

        text = self.normalize_text(raw_text)

        metadata = self.parse_metadata(text)

        blocks = self.extract_licence_blocks(text)

        licences = []

        for block in blocks:
            parsed = self.parse_block(block)

            if parsed["licence_id"]:
                licences.append(parsed)

        return {
            "report_metadata": metadata,
            "well_licences": licences
        }

    def save(self, output_path):

        data = self.build_json()

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return output_path
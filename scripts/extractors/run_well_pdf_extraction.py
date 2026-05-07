import os
from scripts.extractors.pdf_json_well_licence import WellLicencePDFExtractor


SOURCE_PATH = "sources/new_well_license_approvals_coordinates.pdf"
OUTPUT_PATH = "data/processed/well_approvals.json"


def main():

    if not os.path.exists(SOURCE_PATH):
        raise FileNotFoundError(f"Missing file: {SOURCE_PATH}")

    extractor = WellLicencePDFExtractor(SOURCE_PATH)

    output_file = extractor.save(OUTPUT_PATH)

    print(f"Extraction complete: {output_file}")


if __name__ == "__main__":
    main()
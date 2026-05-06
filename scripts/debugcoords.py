import pdfplumber
import os

pdf_path = os.path.join("data", "raw", "spill_report.pdf")
with pdfplumber.open(pdf_path) as pdf:
    first_page = pdf.pages[0]
    # Find words to see their exact coordinates
    words = first_page.extract_words()
    for word in words[:15]:
        print(f"Text: {word['text']} | x0: {word['x0']:.2f} | top: {word['top']:.2f}")
"""OCR extraction from uploaded report images using Tesseract (free, open-source, local),
plus text extraction from PDF reports using pypdf (free, no external service)."""
from PIL import Image
import pytesseract
import pypdf
import io


def extract_text_from_image(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes))
    # Basic preprocessing: convert to grayscale, helps OCR accuracy on scanned/photo reports
    image = image.convert("L")
    text = pytesseract.image_to_string(image)
    return text.strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from a PDF's text layer (works for reports exported/printed as PDF).
    Note: this does NOT do OCR on scanned/image-only PDFs - if a PDF has no text layer,
    this will return an empty string. For scanned PDFs, ask the user to upload a photo instead.
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def extract_text_from_file(file_bytes: bytes, content_type: str) -> str:
    """Routes to the right extractor based on file type."""
    if content_type == "application/pdf":
        return extract_text_from_pdf(file_bytes)
    else:
        return extract_text_from_image(file_bytes)

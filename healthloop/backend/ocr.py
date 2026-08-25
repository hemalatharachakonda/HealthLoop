"""OCR / text extraction from uploaded report files.

Supports:
  - Images (jpg/png/etc) -> Tesseract OCR
  - Text-based PDFs (most hospital-generated PDFs) -> direct text extraction, no OCR needed
  - Scanned/photographed PDFs (no embedded text layer) -> each page is rendered to an
    image and passed through Tesseract, same as a photo

Requires system packages that pip alone does NOT install:
  - tesseract-ocr   (for pytesseract)
  - poppler-utils   (for pdf2image, only needed for scanned PDFs)
These are installed by backend/Dockerfile - make sure the Render service's Environment
is set to Docker, otherwise these binaries won't exist on the server.
"""
from PIL import Image
import pytesseract
import io

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    from pdf2image import convert_from_bytes
except ImportError:  # pragma: no cover
    convert_from_bytes = None


def extract_text_from_image(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("L")  # grayscale - helps OCR accuracy on photos
    text = pytesseract.image_to_string(image)
    return text.strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Try direct text extraction first (fast, free, no OCR needed for digital PDFs).
    Falls back to rendering pages as images + OCR for scanned/photographed PDFs."""
    text_parts = []

    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    text_parts.append(page_text)
        except Exception:
            pass

    combined = "\n".join(text_parts).strip()
    if len(combined) >= 20:
        return combined

    # No usable text layer found - likely a scanned PDF. OCR each page as an image.
    if convert_from_bytes is None:
        raise RuntimeError(
            "This PDF has no selectable text and scanned-PDF support (pdf2image/poppler) "
            "isn't installed on the server."
        )
    pages = convert_from_bytes(pdf_bytes)
    ocr_parts = [pytesseract.image_to_string(p.convert("L")) for p in pages]
    return "\n".join(ocr_parts).strip()


def extract_text_from_file(file_bytes: bytes, content_type: str, filename: str = "") -> str:
    """Routes to the right extractor based on file type."""
    is_pdf = (content_type == "application/pdf") or filename.lower().endswith(".pdf")
    if is_pdf:
        return extract_text_from_pdf(file_bytes)
    return extract_text_from_image(file_bytes)

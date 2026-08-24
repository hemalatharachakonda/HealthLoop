"""OCR extraction from uploaded report images using Tesseract (free, open-source, local)."""
from PIL import Image
import pytesseract
import io


def extract_text_from_image(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes))
    # Basic preprocessing: convert to grayscale, helps OCR accuracy on scanned/photo reports
    image = image.convert("L")
    text = pytesseract.image_to_string(image)
    return text.strip()

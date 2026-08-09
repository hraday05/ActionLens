import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text page-by-page from a PDF file.
    Includes page markers to help the LLM cite specific pages.
    """
    if not os.path.exists(file_path):
        return f"[Error: File not found at {file_path}]"
        
    try:
        doc = fitz.open(file_path)
        extracted_parts = []
        for index, page in enumerate(doc):
            page_text = page.get_text()
            extracted_parts.append(f"--- [Source: {os.path.basename(file_path)}, Page {index + 1}] ---\n{page_text}")
        return "\n\n".join(extracted_parts)
    except Exception as e:
        return f"[Error parsing PDF: {str(e)}]"

def extract_text_from_image(file_path: str) -> str:
    """
    Extracts text from an image or screenshot using pytesseract OCR.
    """
    if not os.path.exists(file_path):
        return f"[Error: File not found at {file_path}]"
        
    try:
        img = Image.open(file_path)
        ocr_text = pytesseract.image_to_string(img)
        return f"--- [Source Image: {os.path.basename(file_path)}] ---\n{ocr_text}"
    except Exception as e:
        # Check if tesseract command is missing
        if "tesseract is not installed" in str(e).lower() or "no such file or directory" in str(e).lower():
            return f"[Error: Tesseract OCR is not installed or not in PATH. Please run 'brew install tesseract' or paste raw text instead. Internal: {str(e)}]"
        return f"[Error parsing image: {str(e)}]"

def extract_content(file_path: str) -> str:
    """
    Main entry point to extract text depending on the file extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"]:
        return extract_text_from_image(file_path)
    else:
        # Fallback for text files or unknown formats
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f"--- [Source File: {os.path.basename(file_path)}] ---\n{f.read()}"
        except Exception as e:
            return f"[Error reading file as text: {str(e)}]"

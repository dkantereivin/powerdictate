"""
Offline Screen OCR & Clipboard Snip Daemon
==========================================
Grabs Citrix Meditech screen snips from the system clipboard or screen region
and passes them through local Tesseract OCR configured for monospace terminal fonts.
"""

from typing import Optional, Union, Dict, Any
from pathlib import Path
from PIL import Image, ImageGrab
import pytesseract

from src.ocr.meditech_parser import MeditechOCRParser, MeditechParsedData


class MeditechOCRService:
    """
    Offline local OCR service for Meditech Citrix screens.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self.parser = MeditechOCRParser()

    def process_image(self, image: Image.Image) -> MeditechParsedData:
        """
        Runs local Tesseract OCR with --psm 6 (Uniform block of text / monospace table).
        """
        # Convert to grayscale and enhance contrast for legacy monospace terminal fonts
        gray_img = image.convert('L')
        # Thresholding to sharpen green/purple terminal pixels against dark background
        raw_text = pytesseract.image_to_string(gray_img, config='--psm 6')
        return self.parser.parse(raw_text)

    def process_clipboard(self) -> Optional[MeditechParsedData]:
        """
        Grabs active image from system clipboard and parses it.
        """
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return self.process_image(img)
        except Exception:
            pass
        return None

    def process_image_file(self, file_path: Union[str, Path]) -> MeditechParsedData:
        """
        Parses an image file on disk.
        """
        img = Image.open(str(file_path))
        return self.process_image(img)

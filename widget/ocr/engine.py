"""
Optical Character Recognition (OCR) Engine
==========================================
High-speed, high-accuracy digital screen and document OCR powered by RapidOCR
(PP-OCRv4 via ONNXRuntime). Optimized for low-resolution hospital terminal
screens, multi-column lab grids, and legacy Citrix fonts.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
import numpy as np
from PIL import Image

logger = logging.getLogger("widget.ocr.engine")


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: List[List[float]]  # 4 corner coordinates [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]

    @property
    def y_center(self) -> float:
        return sum(pt[1] for pt in self.box) / len(self.box)

    @property
    def x_left(self) -> float:
        return min(pt[0] for pt in self.box)


@dataclass
class OcrResult:
    raw_text: str
    lines: List[OcrLine] = field(default_factory=list)
    rows: List[List[OcrLine]] = field(default_factory=list)
    elapse: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not bool(self.raw_text.strip())


class OcrEngine:
    """
    RapidOCR inference wrapper with image normalization and line sorting.
    """

    _instance: Optional["OcrEngine"] = None

    def __init__(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
            self.available = True
            logger.info("RapidOCR initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR: {e}")
            self._ocr = None
            self.available = False

    @classmethod
    def get_instance(cls) -> "OcrEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def recognize(self, image_input: Union[Image.Image, np.ndarray]) -> OcrResult:
        """
        Runs OCR on PIL Image or NumPy array.
        Returns parsed lines sorted in natural top-to-bottom reading order,
        with tokens on the same horizontal row combined with spaces.
        """
        if not self.available or self._ocr is None:
            logger.warning("OCR engine is not available.")
            return OcrResult(raw_text="")

        try:
            # Convert PIL to NumPy if needed
            if isinstance(image_input, Image.Image):
                # Ensure RGB
                if image_input.mode != "RGB":
                    image_input = image_input.convert("RGB")
                img_np = np.array(image_input)
            else:
                img_np = image_input

            result, elapse = self._ocr(img_np)

            if not result:
                return OcrResult(raw_text="", lines=[], rows=[], elapse=elapse)

            lines: List[OcrLine] = []
            for item in result:
                box = item[0]
                text = str(item[1]).strip()
                conf = float(item[2])
                if text:
                    lines.append(OcrLine(text=text, confidence=conf, box=box))

            # Group lines into visual horizontal rows, sorted left-to-right
            rows = self._group_rows(lines)
            sorted_lines: List[OcrLine] = [item for r in rows for item in r]

            # Construct raw_text: each horizontal row is space-separated, rows separated by newline
            raw_text = "\n".join(" ".join(item.text for item in r) for r in rows)

            return OcrResult(raw_text=raw_text, lines=sorted_lines, rows=rows, elapse=elapse)

        except Exception as e:
            logger.error(f"Error during OCR recognition: {e}", exc_info=True)
            return OcrResult(raw_text="")

    def _group_rows(self, lines: List[OcrLine]) -> List[List[OcrLine]]:
        """
        Groups bounding boxes into natural visual reading order:
        Groups items on the same horizontal line together, then sorts each row by X coordinate.
        """
        if not lines:
            return []

        # Sort primarily by Y center
        lines_by_y = sorted(lines, key=lambda l: l.y_center)

        rows: List[List[OcrLine]] = []
        # Estimate typical line height
        heights = [max(pt[1] for pt in l.box) - min(pt[1] for pt in l.box) for l in lines]
        avg_height = sum(heights) / len(heights) if heights else 15
        y_tolerance = max(avg_height * 0.5, 8)

        current_row: List[OcrLine] = [lines_by_y[0]]
        current_y = lines_by_y[0].y_center

        for line in lines_by_y[1:]:
            if abs(line.y_center - current_y) <= y_tolerance:
                current_row.append(line)
            else:
                rows.append(sorted(current_row, key=lambda l: l.x_left))
                current_row = [line]
                current_y = line.y_center

        if current_row:
            rows.append(sorted(current_row, key=lambda l: l.x_left))

        return rows

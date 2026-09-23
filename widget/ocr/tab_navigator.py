"""
Meditech Tab Navigator & Screen Crawler
=======================================
Detects navigation tabs in hospital EMR screens (e.g. Meditech PCI / EMR),
identifies the active tab via background pixel luminance, and enables
autonomous tab navigation to crawl multiple lab panels.
"""

import time
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from widget.ocr.engine import OcrResult, OcrLine
from widget.ocr.meditech_parser import MeditechLabParser, ParsedLabReport

logger = logging.getLogger("widget.ocr.tabs")

MEDITECH_KNOWN_TABS = [
    "Hematology",
    "Coagulation",
    "Urines",
    "Other Body Source",
    "Miscellaneous",
    "Blood Gas",
    "Chemistry",
    "Toxicology",
    "Immunology",
    "Serology",
]


@dataclass
class MeditechTab:
    name: str
    box: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    center_x: int
    center_y: int
    is_active: bool = False


class MeditechTabNavigator:
    """
    Detects navigation buttons on Meditech screen captures and orchestrates
    crawling across multi-page lab inquiries.
    """

    @classmethod
    def detect_tabs(cls, ocr_result: OcrResult, image: Image.Image) -> Dict[str, MeditechTab]:
        """
        Locates all Meditech tabs and identifies which tab is currently active.
        """
        img_np = np.array(image.convert("RGB"))
        img_h, img_w = img_np.shape[:2]
        detected: Dict[str, MeditechTab] = {}

        for line in ocr_result.lines:
            line_text = line.text.strip()
            for tab_name in MEDITECH_KNOWN_TABS:
                matched = False
                if tab_name.lower() == line_text.lower():
                    matched = True
                elif tab_name == "Blood Gas" and "blood" in line_text.lower() and "gas" in line_text.lower():
                    matched = True
                elif tab_name == "Other Body Source" and "other" in line_text.lower() and "source" in line_text.lower():
                    matched = True

                if matched:
                    # Calculate center
                    pts_x = [pt[0] for pt in line.box]
                    pts_y = [pt[1] for pt in line.box]
                    cx = int(sum(pts_x) / len(pts_x))
                    cy = int(sum(pts_y) / len(pts_y))

                    # Determine active state: In Meditech, the active tab has a pure white/light
                    # background (RGB > 240), whereas inactive tabs have a distinct blue tint (R < 200).
                    xmin = max(0, int(min(pts_x)))
                    xmax = min(img_w, int(max(pts_x)))
                    ymin = max(0, int(min(pts_y)))
                    ymax = min(img_h, int(max(pts_y)))

                    crop = img_np[ymin:ymax, xmin:xmax]
                    mean_r = float(np.mean(crop[:, :, 0])) if crop.size > 0 else 0.0

                    detected[tab_name] = MeditechTab(
                        name=tab_name,
                        box=line.box,
                        center_x=cx,
                        center_y=cy,
                        is_active=False  # determined after all tabs are scored
                    )
                    # Store score on temporary attribute
                    detected[tab_name]._score = mean_r
                    break

        # Active tab has the highest luminance (pure white background)
        if detected:
            best_tab = max(detected.values(), key=lambda t: getattr(t, "_score", 0.0))
            if getattr(best_tab, "_score", 0.0) > 200.0:
                best_tab.is_active = True

        return detected

    @classmethod
    def get_active_tab(cls, tabs: Dict[str, MeditechTab]) -> Optional[MeditechTab]:
        for tab in tabs.values():
            if tab.is_active:
                return tab
        return None

    @classmethod
    def crawl_tabs(
        cls,
        tabs: Dict[str, MeditechTab],
        screen_offset: Tuple[int, int],  # (top_left_x, top_left_y) of the captured region on screen
        click_func: Callable[[int, int], None],
        capture_func: Callable[[], Image.Image],
        target_tab_names: Optional[List[str]] = None,
        pause_seconds: float = 0.4
    ) -> List[Image.Image]:
        """
        Crawls through tabs by clicking their screen coordinates, waiting for
        EMR refresh, and capturing screenshots of each page.
        """
        if target_tab_names is None:
            # Default to core lab tabs if present
            priority_tabs = ["Chemistry", "Hematology", "Coagulation", "Blood Gas"]
            target_tab_names = [t for t in priority_tabs if t in tabs]

        captured_images: List[Image.Image] = []
        off_x, off_y = screen_offset

        for tab_name in target_tab_names:
            tab = tabs.get(tab_name)
            if not tab:
                continue

            # Screen absolute coordinate
            abs_x = off_x + tab.center_x
            abs_y = off_y + tab.center_y

            logger.info(f"Navigating to tab '{tab_name}' at ({abs_x}, {abs_y})...")
            click_func(abs_x, abs_y)
            time.sleep(pause_seconds)

            img = capture_func()
            if img:
                captured_images.append(img)

        return captured_images

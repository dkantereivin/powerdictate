"""
Base Print Template Interface
==============================
Defines the abstract interface for all clinical print templates,
producing HTML (for vector PDF / print preview) and DOCX (for editable Word export).
"""

from abc import ABC, abstractmethod
from typing import Optional
import docx
from printing.models import ClinicalNote


class BasePrintTemplate(ABC):
    """Abstract base class for clinical print templates."""

    template_id: str = "base"
    name: str = "Base Template"
    description: str = "Abstract base template"

    @abstractmethod
    def render_html(self, note: ClinicalNote) -> str:
        """Renders the clinical note as styled HTML for vector PDF and print preview."""
        pass

    @abstractmethod
    def render_docx(self, note: ClinicalNote) -> docx.Document:
        """Renders the clinical note as a native Microsoft Word .docx document."""
        pass

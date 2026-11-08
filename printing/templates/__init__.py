"""
Clinical Print Templates Registry
=================================
Manages registration and lookup of clinical document templates:
- TBRHSC Consult Note
- Progress Note
- Clean Standard Note
"""

from typing import Dict, List, Optional
from printing.templates.base import BasePrintTemplate
from printing.templates.tbrhsc_consult import TBRHSCConsultTemplate
from printing.templates.progress_note import ProgressNoteTemplate
from printing.templates.clean_note import CleanNoteTemplate


TEMPLATES: Dict[str, BasePrintTemplate] = {
    "tbrhsc_consult": TBRHSCConsultTemplate(),
    "progress_note": ProgressNoteTemplate(),
    "clean_note": CleanNoteTemplate(),
}

DEFAULT_TEMPLATE_ID = "tbrhsc_consult"


def get_template(template_id: Optional[str] = None) -> BasePrintTemplate:
    """Returns requested template or falls back to default TBRHSC Consult Note."""
    if not template_id:
        return TEMPLATES[DEFAULT_TEMPLATE_ID]

    tid = template_id.strip().lower()
    if tid in TEMPLATES:
        return TEMPLATES[tid]

    # Search by template name
    for t_obj in TEMPLATES.values():
        if t_obj.name.lower() == tid or tid in t_obj.name.lower():
            return t_obj

    return TEMPLATES[DEFAULT_TEMPLATE_ID]


def list_templates() -> List[Dict[str, str]]:
    """Returns available templates with id, display name, and description."""
    return [
        {
            "id": t.template_id,
            "name": t.name,
            "description": t.description
        }
        for t in TEMPLATES.values()
    ]

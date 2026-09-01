"""
Dynamic YAML / JSON Clinical Template & Macro Manager
======================================================
Loads, parses, and manages multi-user clinical note templates and dot-phrases
from YAML / JSON files in the templates directory.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import datetime


TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


class TemplateManager:
    """
    Manages external YAML and JSON template files.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> List[Dict[str, Any]]:
        """Returns metadata for all available templates."""
        results = []
        for file in self.templates_dir.glob("*.yaml"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        results.append({
                            "id": data.get("id", file.stem),
                            "name": data.get("name", file.stem),
                            "category": data.get("category", "General"),
                            "description": data.get("description", ""),
                            "filename": file.name
                        })
            except Exception:
                pass
        return results

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Loads a specific template by ID, replacing dynamic variables like {DATE}."""
        target_file = self.templates_dir / f"{template_id}.yaml"
        if not target_file.exists():
            return None

        with open(target_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "content" in data:
                today_str = datetime.date.today().strftime("%B %d, %Y")
                data["content"] = data["content"].replace("{DATE}", today_str)
            return data

    def save_template(self, template_data: Dict[str, Any]) -> str:
        """Saves or updates a template YAML file."""
        template_id = template_data.get("id", "").strip()
        if not template_id:
            raise ValueError("Template must have an 'id'")

        target_file = self.templates_dir / f"{template_id}.yaml"
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(template_data, f, sort_keys=False)
        return template_id

    def load_macros(self) -> Dict[str, Any]:
        """Loads macros from macros.json."""
        macros_file = self.templates_dir / "macros.json"
        if not macros_file.exists():
            return {}
        with open(macros_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_macro(self, macro_dict: Dict[str, Any]) -> str:
        """Adds or updates a macro in macros.json."""
        macro_id = macro_dict.get("id", "").strip()
        if not macro_id:
            raise ValueError("Macro must have an 'id'")

        current_macros = self.load_macros()
        current_macros[macro_id] = macro_dict

        macros_file = self.templates_dir / "macros.json"
        with open(macros_file, "w", encoding="utf-8") as f:
            json.dump(current_macros, f, indent=2)
        return macro_id

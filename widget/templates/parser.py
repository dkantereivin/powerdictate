"""
Template Field Parser & Default Resolver
========================================
Parses clinical template fields:
- Wildcards: [***]
- Defaults: [No], [2g sodium]
- Picklists: [No/Yes], [DOAC/LMWH/Warfarin]
- Choice with free-text: [***/DOAC/LMWH/Warfarin]
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


class FieldType(Enum):
    WILDCARD = "WILDCARD"                      # [***]
    DEFAULT = "DEFAULT"                        # [No]
    PICKLIST = "PICKLIST"                      # [No/Yes], [A/B/C]
    WILDCARD_PICKLIST = "WILDCARD_PICKLIST"    # [***/A/B]


@dataclass
class TemplateField:
    raw_text: str
    field_type: FieldType
    options: List[str]
    default_value: str
    start_pos: int
    end_pos: int

    @property
    def has_default(self) -> bool:
        return bool(self.default_value and self.default_value != "***")

    @property
    def display_options(self) -> List[str]:
        return [o for o in self.options if o != "***"]

    @property
    def is_choice(self) -> bool:
        """True if there are multiple options for the clinician to select."""
        return len(self.display_options) > 1


class TemplateParser:
    """
    Scans, parses, and resolves clinical template fields and picklists.
    """

    PATTERN = re.compile(r'\[([^\]\n]+)\]')

    @classmethod
    def parse_field_string(cls, bracket_text: str) -> Optional[TemplateField]:
        """Parses a single bracketed string, e.g. '[No/Yes]'."""
        if not bracket_text.startswith("[") or not bracket_text.endswith("]"):
            return None

        inner = bracket_text[1:-1].strip()
        if not inner:
            return None

        if inner == "***":
            return TemplateField(
                raw_text=bracket_text,
                field_type=FieldType.WILDCARD,
                options=[],
                default_value="",
                start_pos=0,
                end_pos=len(bracket_text)
            )

        if "/" in inner:
            opts = [o.strip() for o in inner.split("/") if o.strip()]
            if opts and opts[0] == "***":
                return TemplateField(
                    raw_text=bracket_text,
                    field_type=FieldType.WILDCARD_PICKLIST,
                    options=opts,
                    default_value="",
                    start_pos=0,
                    end_pos=len(bracket_text)
                )
            else:
                default = opts[0] if opts else ""
                return TemplateField(
                    raw_text=bracket_text,
                    field_type=FieldType.PICKLIST,
                    options=opts,
                    default_value=default,
                    start_pos=0,
                    end_pos=len(bracket_text)
                )

        # Single default value (e.g. [No] or [Daily])
        return TemplateField(
            raw_text=bracket_text,
            field_type=FieldType.DEFAULT,
            options=[inner],
            default_value=inner,
            start_pos=0,
            end_pos=len(bracket_text)
        )

    @classmethod
    def parse_fields(cls, text: str) -> List[TemplateField]:
        """Finds and parses all bracket fields in text with exact string positions."""
        fields: List[TemplateField] = []
        for m in cls.PATTERN.finditer(text):
            raw = m.group(0)
            inner = m.group(1).strip()
            start = m.start()
            end = m.end()

            if inner == "***":
                ftype = FieldType.WILDCARD
                opts = []
                default = ""
            elif "/" in inner:
                opts = [o.strip() for o in inner.split("/") if o.strip()]
                if opts and opts[0] == "***":
                    ftype = FieldType.WILDCARD_PICKLIST
                    default = ""
                else:
                    ftype = FieldType.PICKLIST
                    default = opts[0] if opts else ""
            else:
                ftype = FieldType.DEFAULT
                opts = [inner]
                default = inner

            fields.append(TemplateField(
                raw_text=raw,
                field_type=ftype,
                options=opts,
                default_value=default,
                start_pos=start,
                end_pos=end
            ))

        return fields

    @classmethod
    def resolve_all_defaults(cls, text: str) -> Tuple[str, int]:
        """
        Resolves all defaults across the text for note transfer:
        - [No] -> No
        - [No/Yes] -> No
        - [2g sodium] -> 2g sodium
        - [***] -> kept intact (or counted as unfilled wildcards)
        Returns (resolved_text, unfilled_wildcard_count).
        """
        unfilled_wildcards = 0

        def replace_match(m):
            nonlocal unfilled_wildcards
            raw = m.group(0)
            inner = m.group(1).strip()

            if inner == "***":
                unfilled_wildcards += 1
                return raw  # Leave [***] for clinician to notice

            if "/" in inner:
                opts = [o.strip() for o in inner.split("/") if o.strip()]
                if all(opt.isdigit() for opt in opts):
                    # Dates or numeric bracket citations like [12/15/2024]
                    return raw
                if opts and opts[0] == "***":
                    unfilled_wildcards += 1
                    return "[***]"
                elif opts:
                    # First option is the default
                    return opts[0]
                return raw

            # Single default value: strip brackets
            return inner

        resolved = cls.PATTERN.sub(replace_match, text)
        return resolved, unfilled_wildcards

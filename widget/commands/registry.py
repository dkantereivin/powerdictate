"""
Extensible Voice Command Registry (Python & YAML)
=================================================
Allows voice commands to be defined via:
1. rules/commands.yaml (simple keyboard shortcuts / actions)
2. Python functions via @register_command (for complex logic, EMR macros, etc.)
"""

import sys
import time
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("widget.commands.registry")

COMMANDS_YAML = Path(__file__).resolve().parent.parent.parent / "rules" / "commands.yaml"


@dataclass
class CommandDefinition:
    name: str
    triggers: List[str]
    hotkey: str = ""
    action: str = ""
    description: str = ""
    template_text: str = ""
    handler: Optional[Callable[[str, Any], bool]] = None


# Global registry of Python commands
_PYTHON_COMMAND_REGISTRY: Dict[str, CommandDefinition] = {}


def register_command(
    triggers: List[str] | str,
    name: str = "",
    hotkey: str = "",
    description: str = "",
    template_text: str = ""
):
    """
    Decorator to register a custom Python function or template as a voice command.
    """
    if isinstance(triggers, str):
        triggers = [triggers]

    clean_triggers = [t.strip().lower() for t in triggers if t.strip()]

    def decorator(fn: Callable[[str, Any], bool]):
        cmd_name = name or (clean_triggers[0].title() if clean_triggers else fn.__name__)
        cmd_def = CommandDefinition(
            name=cmd_name,
            triggers=clean_triggers,
            hotkey=hotkey,
            action="custom_python",
            description=description or fn.__doc__ or "",
            template_text=template_text,
            handler=fn
        )
        for trig in clean_triggers:
            _PYTHON_COMMAND_REGISTRY[trig] = cmd_def
            logger.info(f"Registered custom Python voice command: '{trig}' -> {cmd_name}")
        return fn

    return decorator


class CommandRegistry:
    """
    Unified manager combining YAML commands, templates, and Python function commands.
    """

    def __init__(self, yaml_path: Optional[Path] = None):
        self.yaml_path = yaml_path or COMMANDS_YAML
        self.commands: Dict[str, CommandDefinition] = {}
        self.reload()

    def reload(self):
        """Loads YAML definitions and merges with registered Python commands."""
        self.commands.clear()

        # 1. Load from YAML
        if self.yaml_path.exists():
            try:
                with open(self.yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                    # Load standard commands
                    yaml_cmds = data.get("commands", {})
                    for trigger, info in yaml_cmds.items():
                        clean_trigger = trigger.strip().lower()
                        template_content = info.get("text", "") or info.get("template", "")
                        self.commands[clean_trigger] = CommandDefinition(
                            name=info.get("name", clean_trigger.title()),
                            triggers=[clean_trigger],
                            hotkey=info.get("hotkey", ""),
                            action=info.get("action", "insert_template" if template_content else ""),
                            description=info.get("description", ""),
                            template_text=template_content
                        )

                    # Load clinical & document templates
                    yaml_templates = data.get("templates", {})
                    for trigger, info in yaml_templates.items():
                        clean_trigger = trigger.strip().lower()
                        if isinstance(info, str):
                            template_content = info
                            tpl_name = clean_trigger.title()
                            tpl_desc = f"Template: {tpl_name}"
                        else:
                            template_content = info.get("text", "") or info.get("template", "")
                            tpl_name = info.get("name", clean_trigger.title())
                            tpl_desc = info.get("description", f"Template: {tpl_name}")

                        tpl_def = CommandDefinition(
                            name=tpl_name,
                            triggers=[clean_trigger],
                            hotkey="",
                            action="insert_template",
                            description=tpl_desc,
                            template_text=template_content
                        )
                        self.commands[clean_trigger] = tpl_def
                        # Support natural "insert <template>" alias
                        if not clean_trigger.startswith("insert "):
                            self.commands[f"insert {clean_trigger}"] = tpl_def

                    logger.info(f"Loaded {len(self.commands)} commands & templates from {self.yaml_path.name}")
            except Exception as e:
                logger.error(f"Error loading {self.yaml_path}: {e}")

        # 2. Merge Python commands (Python overrides/augments YAML)
        for trigger, cmd_def in _PYTHON_COMMAND_REGISTRY.items():
            self.commands[trigger] = cmd_def

    def get_command(self, trigger: str) -> Optional[CommandDefinition]:
        """Looks up command by trigger, stripping surrounding brackets/quotes."""
        if not trigger:
            return None

        clean = trigger.strip("[]()\"'.,?!:; ").lower()
        return self.commands.get(clean)

    def list_triggers(self) -> List[str]:
        """Returns all recognized command trigger strings."""
        return list(self.commands.keys())

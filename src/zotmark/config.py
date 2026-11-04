from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from zotmark.models import CategoryRule


@dataclass
class SyncSettings:
    preserve_user_notes: bool = True
    user_content_marker: str = "<!-- USER_CONTENT_START -->"
    include_annotations: bool = True
    include_abstract: bool = True


@dataclass
class AppConfig:
    notes_path: str = "~/Notes"
    default_output_dir: str = "Literature"
    file_name_format: str = "{{ citekey }}"
    zotero_api_url: str = "http://127.0.0.1:23119"
    zotero_db_path: str = "~/Zotero/zotero.sqlite"
    categories: list[CategoryRule] = field(default_factory=list)
    sync: SyncSettings = field(default_factory=SyncSettings)

    @property
    def vault_path(self) -> str:
        """Backwards compatibility alias for notes_path."""
        return self.notes_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "notes_path": str(self.notes_path),
            "default_output_dir": self.default_output_dir,
            "file_name_format": self.file_name_format,
            "zotero": {
                "api_url": self.zotero_api_url,
                "db_path": str(self.zotero_db_path),
            },
            "categories": [
                {
                    "name": cat.name,
                    "match": {
                        **({"collection": cat.match_collection} if cat.match_collection else {}),
                        **({"item_type": cat.match_item_type} if cat.match_item_type else {}),
                    },
                    "output_dir": cat.output_dir,
                    "template": cat.template,
                    "enabled": cat.enabled,
                }
                for cat in self.categories
            ],
            "sync": asdict(self.sync),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        zotero_data = data.get("zotero", {})
        sync_data = data.get("sync", {})

        categories = []
        for cat_data in data.get("categories", []):
            match_data = cat_data.get("match", {})
            categories.append(
                CategoryRule(
                    name=cat_data.get("name", "Untitled Rule"),
                    match_collection=match_data.get("collection"),
                    match_item_type=match_data.get("item_type"),
                    output_dir=cat_data.get("output_dir", "Literature"),
                    template=cat_data.get("template", "templates/paper.md.j2"),
                    enabled=cat_data.get("enabled", True),
                )
            )

        sync_settings = SyncSettings(
            preserve_user_notes=sync_data.get("preserve_user_notes", True),
            user_content_marker=sync_data.get("user_content_marker", "<!-- USER_CONTENT_START -->"),
            include_annotations=sync_data.get("include_annotations", True),
            include_abstract=sync_data.get("include_abstract", True),
        )

        resolved_notes_path = data.get("notes_path") or data.get("vault_path") or "~/Notes"

        return cls(
            notes_path=resolved_notes_path,
            default_output_dir=data.get("default_output_dir", "Literature"),
            file_name_format=data.get("file_name_format", "{{ citekey }}"),
            zotero_api_url=zotero_data.get("api_url", "http://127.0.0.1:23119"),
            zotero_db_path=zotero_data.get("db_path", "~/Zotero/zotero.sqlite"),
            categories=categories,
            sync=sync_settings,
        )


def render_commented_yaml(config: AppConfig) -> str:
    """Render AppConfig into an extensively commented, human-friendly YAML string."""
    lines = [
        "# ==============================================================================",
        "# Zotmark Configuration File",
        "# Online Guide: https://github.com/abakierkan/zotmark/blob/main/docs/CONFIGURATION_AND_SETUP.md",
        "# ==============================================================================",
        "",
        "# ------------------------------------------------------------------------------",
        "# 1. Notes Directory Settings",
        "# ------------------------------------------------------------------------------",
        "# Root directory where your Markdown notes or literature repository is stored.",
        f'notes_path: "{config.notes_path}"',
        "",
        "# Default destination folder inside notes_path (relative to notes_path).",
        f'default_output_dir: "{config.default_output_dir}"',
        "",
        "# File naming pattern using Jinja2 syntax (.md is added automatically).",
        "#",
        "# Available variables:",
        "#   {{ citekey }} -> Better BibTeX citation key (e.g. willingham-2008-critical-thinking-why)",
        "#   {{ key }}     -> 8-character Zotero item key (e.g. JPAZLXQ2)",
        "#   {{ title }}   -> Sanitized publication title",
        "#   {{ year }}    -> 4-digit publication year (or 'nodate')",
        "#   {{ author }}  -> First author's last name (or 'anon')",
        "#",
        "# Examples:",
        "#   \"{{ citekey }}\"            -> willingham-2008-critical-thinking-why.md",
        "#   \"@{{ citekey }}\"           -> @willingham-2008-critical-thinking-why.md",
        "#   \"{{ year }} - {{ title }}\" -> 2008 - Critical Thinking Why Is It So Hard to Teach.md",
        f'file_name_format: "{config.file_name_format}"',
        "",
        "# ------------------------------------------------------------------------------",
        "# 2. Zotero Connection Settings",
        "# ------------------------------------------------------------------------------",
        "zotero:",
        "  # Base URL for local Zotero Desktop API (port 23119 by default)",
        f'  api_url: "{config.zotero_api_url}"',
        "  # Path to local Zotero SQLite database.",
        "  # Automatically used as a zero-lock read-only fallback when Zotero is closed.",
        f'  db_path: "{config.zotero_db_path}"',
        "",
        "# ------------------------------------------------------------------------------",
        "# 3. Category & Template Routing Rules",
        "# ------------------------------------------------------------------------------",
        "# Each rule determines:",
        "#   - Which items match (by Zotero collection name, item_type, or both)",
        "#   - Where to place the note ('output_dir', relative to notes_path)",
        "#   - Which Jinja2 template to render ('template')",
        "#",
        "# Rules are evaluated sequentially from TOP to BOTTOM.",
        "# The FIRST rule that matches an item determines its destination!",
        "#",
        "# CHEAT SHEET - Common Zotero item_type tags:",
        "#   journalArticle   - Academic journal articles",
        "#   preprint         - Preprints (arXiv, bioRxiv, medRxiv, SSRN, etc.)",
        "#   conferencePaper  - Conference papers and proceedings",
        "#   book             - Books",
        "#   bookSection      - Book chapters or sections",
        "#   thesis           - Master's theses and Ph.D. dissertations",
        "#   report           - Whitepapers, institutional reports, technical reports",
        "#   webpage          - Web articles and blog posts",
        "#   manuscript       - Unpublished manuscripts",
        "#   patent           - Patents",
        "#",
        "# Available built-in templates:",
        "#   templates/paper.md.j2   - Optimized for scientific papers (DOIs, journal, PDF highlights)",
        "#   templates/book.md.j2    - Optimized for books (publisher, ISBN, reading notes)",
        "#   templates/default.md.j2 - Clean generic fallback for any item",
        "categories:",
    ]

    for cat in config.categories:
        lines.append(f'  - name: "{cat.name}"')
        has_match = bool(cat.match_collection or cat.match_item_type)
        if has_match:
            lines.append("    match:")
            if cat.match_collection:
                lines.append(f'      collection: "{cat.match_collection}"  # Zotero collection name')
            if cat.match_item_type:
                if isinstance(cat.match_item_type, list):
                    lines.append("      item_type:  # Matches any of these item types")
                    for t in cat.match_item_type:
                        lines.append(f'        - "{t}"')
                else:
                    lines.append(f'      item_type: "{cat.match_item_type}"')
        lines.append(f'    output_dir: "{cat.output_dir}"  # Target folder in notes_path')
        lines.append(f'    template: "{cat.template}"  # Jinja2 template path')
        lines.append(f'    enabled: {str(cat.enabled).lower()}  # Set false to temporarily disable')
        lines.append("")

    lines.extend([
        "# ------------------------------------------------------------------------------",
        "# 4. Sync Behavior Settings",
        "# ------------------------------------------------------------------------------",
        "sync:",
        "  # When true, notes written below 'user_content_marker' will NEVER be overwritten!",
        f"  preserve_user_notes: {str(config.sync.preserve_user_notes).lower()}",
        "",
        "  # Boundary delimiter separating generated reference metadata from personal notes.",
        f'  user_content_marker: "{config.sync.user_content_marker}"',
        "",
        "  # Whether to extract and include PDF highlights and comments from Zotero",
        f"  include_annotations: {str(config.sync.include_annotations).lower()}",
        "",
        "  # Whether to include publication abstract in the note",
        f"  include_abstract: {str(config.sync.include_abstract).lower()}",
        "",
    ])

    return "\n".join(lines)


def find_config_path(explicit_path: str | Path | None = None) -> Path:
    """Find config.yaml in current dir, user config dir, or default location."""
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    locations = [
        Path.cwd() / "config.yaml",
        Path.home() / ".config" / "zotmark" / "config.yaml",
    ]
    for loc in locations:
        if loc.exists():
            return loc

    return Path.cwd() / "config.yaml"


def load_config(path: str | Path | None = None) -> AppConfig:
    config_file = find_config_path(path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}. Run 'zotmark init' first.")
    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: str | Path | None = None) -> Path:
    config_file = find_config_path(path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    content = render_commented_yaml(config)
    config_file.write_text(content, encoding="utf-8")
    return config_file

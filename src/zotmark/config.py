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
    vault_path: str = "/home/xenologos/Koofr/obsidian"
    default_output_dir: str = "02-Records/Literature"
    file_name_format: str = "@{{ citekey }}"
    zotero_api_url: str = "http://127.0.0.1:23119"
    zotero_db_path: str = "~/Zotero/zotero.sqlite"
    categories: list[CategoryRule] = field(default_factory=list)
    sync: SyncSettings = field(default_factory=SyncSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vault_path": str(self.vault_path),
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
                    output_dir=cat_data.get("output_dir", "02-Records/Literature"),
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

        return cls(
            vault_path=data.get("vault_path", "/home/xenologos/Koofr/obsidian"),
            default_output_dir=data.get("default_output_dir", "02-Records/Literature"),
            file_name_format=data.get("file_name_format", "@{{ citekey }}"),
            zotero_api_url=zotero_data.get("api_url", "http://127.0.0.1:23119"),
            zotero_db_path=zotero_data.get("db_path", "~/Zotero/zotero.sqlite"),
            categories=categories,
            sync=sync_settings,
        )


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
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config.to_dict(), f, sort_keys=False, indent=2, allow_unicode=True)
    return config_file

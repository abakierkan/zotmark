from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zotmark.config import AppConfig
from zotmark.models import CategoryRule, ZoteroItem
from zotmark.template_engine import TemplateEngine
from zotmark.zotero_client import ZoteroClient

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    total_evaluated: int = 0
    created: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


class SyncEngine:
    def __init__(self, config: AppConfig, client: ZoteroClient | None = None):
        self.config = config
        self.vault_path = Path(config.vault_path).expanduser().resolve()
        self.client = client or ZoteroClient(
            api_base_url=config.zotero_api_url,
            db_path=config.zotero_db_path,
        )
        self.template_engine = TemplateEngine(
            template_dirs=[Path(self.config.vault_path) / "templates"]
        )
        self._collections_map: dict[str, str] = {}

    def _ensure_collections_map(self) -> None:
        if not self._collections_map:
            collections = self.client.get_collections()
            self._collections_map = {c.key: c.name for c in collections}

    def match_rule(self, item: ZoteroItem) -> CategoryRule | None:
        """Find the first matching category rule for an item."""
        self._ensure_collections_map()
        for rule in self.config.categories:
            if rule.matches(item, self._collections_map):
                return rule
        return None

    def sync_items(
        self,
        items: list[ZoteroItem],
        dry_run: bool = False,
        force: bool = False,
    ) -> SyncStats:
        """Synchronize a list of items to the Obsidian vault."""
        stats = SyncStats()
        self._ensure_collections_map()

        for item in items:
            stats.total_evaluated += 1
            rule = self.match_rule(item)
            if not rule:
                stats.skipped += 1
                continue

            try:
                target_dir = self.vault_path / rule.output_dir
                filename = self.template_engine.render_filename(
                    self.config.file_name_format, item
                )
                file_path = target_dir / filename

                rendered_content = self.template_engine.render_item(
                    template_name_or_path=rule.template,
                    item=item,
                    extra_vars={"user_content_marker": self.config.sync.user_content_marker},
                )

                if file_path.exists():
                    existing_content = file_path.read_text(encoding="utf-8")
                    merged_content = self._merge_user_content(
                        existing_content, rendered_content
                    )

                    if not force and existing_content.strip() == merged_content.strip():
                        stats.skipped += 1
                        continue

                    if not dry_run:
                        file_path.write_text(merged_content, encoding="utf-8")
                    stats.updated.append(file_path)
                else:
                    if not dry_run:
                        target_dir.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(rendered_content, encoding="utf-8")
                    stats.created.append(file_path)

            except Exception as e:
                logger.error(f"Error syncing {item.key} ({item.title}): {e}")
                stats.errors.append((item.key, str(e)))

        return stats

    def _merge_user_content(self, existing: str, new_rendered: str) -> str:
        """Preserve any user modifications made below user_content_marker."""
        if not self.config.sync.preserve_user_notes:
            return new_rendered

        marker = self.config.sync.user_content_marker

        # Check if existing file has the marker
        if marker in existing:
            parts = existing.split(marker, 1)
            user_notes = parts[1]
            if marker in new_rendered:
                new_head = new_rendered.split(marker, 1)[0]
                return f"{new_head}{marker}{user_notes}"
            else:
                return f"{new_rendered}\n\n{marker}{user_notes}"

        # If existing file doesn't have the marker, preserve all non-frontmatter text
        return f"{new_rendered}\n\n{marker}\n## Preserved Notes\n\n{existing}"

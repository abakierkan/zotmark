from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template

from zotmark.models import ZoteroItem


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as a filename."""
    # Remove characters illegal in Linux/Windows filenames
    sanitized = re.sub(r'[/\\:*?"<>|]', "", name)
    sanitized = sanitized.replace("\n", " ").replace("\r", " ").strip()
    return sanitized or "untitled"


class TemplateEngine:
    def __init__(self, template_dirs: list[Path | str] | None = None):
        search_paths = []
        if template_dirs:
            for p in template_dirs:
                resolved = Path(p).expanduser().resolve()
                if resolved.exists():
                    search_paths.append(str(resolved))

        # Always include project default templates directory
        default_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        if default_dir.exists() and str(default_dir) not in search_paths:
            search_paths.append(str(default_dir))

        cwd_templates = Path.cwd() / "templates"
        if cwd_templates.exists() and str(cwd_templates) not in search_paths:
            search_paths.append(str(cwd_templates))

        self.env = Environment(
            loader=FileSystemLoader(search_paths) if search_paths else None,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        self.env.filters["sanitize_filename"] = sanitize_filename

    def render_item(
        self,
        template_name_or_path: str,
        item: ZoteroItem,
        extra_vars: dict[str, Any] | None = None,
    ) -> str:
        """Render a ZoteroItem using the specified Jinja2 template."""
        template_path = Path(template_name_or_path)

        # If it's a direct file path that exists, load directly
        if template_path.exists() and template_path.is_file():
            with open(template_path, "r", encoding="utf-8") as f:
                template = self.env.from_string(f.read())
        else:
            # Look up via template loader (e.g. "paper.md.j2" or "templates/paper.md.j2")
            name = template_path.name
            template = self.env.get_template(name)

        context: dict[str, Any] = {
            "key": item.key,
            "citekey": item.citekey,
            "title": item.title,
            "authors": item.authors,
            "authors_string": item.authors_string,
            "year": item.year,
            "date": item.date,
            "date_added": item.date_added,
            "date_modified": item.date_modified,
            "publication_title": item.publication_title,
            "publisher": item.publisher,
            "volume": item.volume,
            "issue": item.issue,
            "pages": item.pages,
            "doi": item.doi,
            "url": item.url,
            "isbn": item.isbn,
            "abstract": item.abstract,
            "tags": item.tags,
            "collections": item.collections,
            "pdf_path": item.pdf_path,
            "annotations": item.annotations,
            "user_content_marker": "<!-- USER_CONTENT_START -->",
        }
        if extra_vars:
            context.update(extra_vars)

        return template.render(**context)

    def render_filename(self, filename_format: str, item: ZoteroItem) -> str:
        """Render the note filename according to user format, e.g. '@{{ citekey }}'."""
        tmpl = self.env.from_string(filename_format)
        rendered = tmpl.render(
            citekey=item.citekey or item.key,
            key=item.key,
            title=item.title,
            year=item.year or "nodate",
            author=item.authors[0] if item.authors else "anon",
        )
        safe = sanitize_filename(rendered)
        if not safe.endswith(".md"):
            safe += ".md"
        return safe

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Annotation:
    key: str
    text: str | None
    comment: str | None
    color: str | None
    page: str | None
    annotation_type: str = "highlight"


@dataclass
class CollectionInfo:
    key: str
    name: str
    parent_key: str | None = None
    num_items: int = 0


@dataclass
class ZoteroItem:
    key: str
    version: int
    item_type: str
    title: str
    creators: list[dict[str, Any]] = field(default_factory=list)
    date: str | None = None
    year: str | None = None
    publication_title: str | None = None
    publisher: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    isbn: str | None = None
    abstract: str | None = None
    citekey: str = ""
    collections: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    date_added: str = ""
    date_modified: str = ""
    pdf_path: str | None = None
    annotations: list[Annotation] = field(default_factory=list)

    @property
    def authors(self) -> list[str]:
        result = []
        for c in self.creators:
            if c.get("creatorType") in ("author", "editor", "contributor", "programmer", None):
                first = c.get("firstName", "").strip()
                last = c.get("lastName", "").strip()
                name = c.get("name", "").strip()
                if first and last:
                    result.append(f"{first} {last}")
                elif last:
                    result.append(last)
                elif name:
                    result.append(name)
        return result

    @property
    def authors_string(self) -> str:
        auths = self.authors
        if not auths:
            return "Unknown"
        if len(auths) == 1:
            return auths[0]
        if len(auths) == 2:
            return f"{auths[0]} & {auths[1]}"
        if len(auths) > 3:
            return f"{auths[0]} et al."
        return ", ".join(auths)

    @classmethod
    def clean_html(cls, text: str | None) -> str | None:
        if not text:
            return text
        cleaned = re.sub(r"<[^>]+>", "", text).strip()
        return cleaned


@dataclass
class CategoryRule:
    name: str
    match_collection: str | None = None
    match_item_type: list[str] | str | None = None
    output_dir: str = "02-Records/Literature"
    template: str = "templates/paper.md.j2"
    enabled: bool = True

    def matches(self, item: ZoteroItem, collection_names_by_key: dict[str, str]) -> bool:
        if not self.enabled:
            return False

        # Match by collection name or collection key
        if self.match_collection:
            item_coll_names = [
                collection_names_by_key.get(k, k).lower() for k in item.collections
            ]
            target_coll = self.match_collection.lower()
            if not any(target_coll == c or target_coll in c for c in item_coll_names):
                return False

        # Match by item type
        if self.match_item_type:
            types = (
                [self.match_item_type.lower()]
                if isinstance(self.match_item_type, str)
                else [t.lower() for t in self.match_item_type]
            )
            if item.item_type.lower() not in types:
                return False

        return True

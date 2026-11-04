from __future__ import annotations

import json
import logging
import re
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from zotmark.models import Annotation, CollectionInfo, ZoteroItem

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Client for interacting with Zotero via HTTP API or SQLite fallback."""

    def __init__(
        self,
        api_base_url: str = "http://127.0.0.1:23119",
        db_path: str | Path | None = None,
        storage_dir: str | Path | None = None,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.db_path = (
            Path(db_path).expanduser().resolve()
            if db_path
            else Path.home() / "Zotero" / "zotero.sqlite"
        )
        self.storage_dir = (
            Path(storage_dir).expanduser().resolve()
            if storage_dir
            else Path.home() / "Zotero" / "storage"
        )
        self._is_api_available: bool | None = None

    def check_api_available(self) -> bool:
        """Check if Zotero Desktop API is running and reachable."""
        if self._is_api_available is not None:
            return self._is_api_available
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(f"{self.api_base_url}/api/users/0/items?limit=1")
                self._is_api_available = res.status_code == 200
        except Exception:
            self._is_api_available = False
        return self._is_api_available

    # ==========================================
    # Collections & Categories Discovery
    # ==========================================

    def get_collections(self) -> list[CollectionInfo]:
        """Fetch all collections from Zotero."""
        if self.check_api_available():
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.get(f"{self.api_base_url}/api/users/0/collections")
                    res.raise_for_status()
                    data = res.json()
                    collections = []
                    for c in data:
                        c_data = c.get("data", {})
                        c_meta = c.get("meta", {})
                        collections.append(
                            CollectionInfo(
                                key=c_data.get("key", c.get("key", "")),
                                name=c_data.get("name", "Untitled"),
                                parent_key=c_data.get("parentCollection") or None,
                                num_items=c_meta.get("numItems", 0),
                            )
                        )
                    return sorted(collections, key=lambda x: x.name.lower())
            except Exception as e:
                logger.warning(f"Failed to fetch collections via API ({e}), falling back to SQLite.")

        return self._get_collections_sqlite()

    def _get_collections_sqlite(self) -> list[CollectionInfo]:
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT c.key, c.collectionName as name, p.key as parent_key,
                       (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as num_items
                FROM collections c
                LEFT JOIN collections p ON c.parentCollectionID = p.collectionID
                ORDER BY c.collectionName
                """
            ).fetchall()
            return [
                CollectionInfo(
                    key=r["key"],
                    name=r["name"],
                    parent_key=r["parent_key"],
                    num_items=r["num_items"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_item_types(self) -> dict[str, int]:
        """Get summary of item types in the library with counts."""
        if self.db_path.exists():
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT it.typeName, COUNT(*) as cnt
                    FROM items i
                    JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                    WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
                    GROUP BY it.typeName
                    ORDER BY cnt DESC
                    """
                ).fetchall()
                return {r["typeName"]: r["cnt"] for r in rows}
            finally:
                conn.close()
        return {}

    # ==========================================
    # Items Retrieval
    # ==========================================

    def get_items(
        self,
        limit: int | None = None,
        keys: list[str] | None = None,
        collection_key: str | None = None,
        since_version: int | None = None,
    ) -> list[ZoteroItem]:
        """Fetch items matching criteria, including annotations and attachments."""
        if self.check_api_available():
            try:
                items = self._get_items_api(
                    limit=limit,
                    keys=keys,
                    collection_key=collection_key,
                    since_version=since_version,
                )
                self._attach_annotations_and_files(items)
                return items
            except Exception as e:
                logger.warning(f"API fetch failed ({e}), falling back to SQLite.")

        items = self._get_items_sqlite(
            limit=limit,
            keys=keys,
            collection_key=collection_key,
            since_version=since_version,
        )
        self._attach_annotations_and_files_sqlite(items)
        return items

    def _get_items_api(
        self,
        limit: int | None = None,
        keys: list[str] | None = None,
        collection_key: str | None = None,
        since_version: int | None = None,
    ) -> list[ZoteroItem]:
        client = httpx.Client(timeout=30.0)
        results: list[ZoteroItem] = []

        try:
            if keys:
                for k in keys:
                    res = client.get(f"{self.api_base_url}/api/users/0/items/{k}")
                    if res.status_code == 200:
                        results.append(self._parse_api_item(res.json()))
                return results

            # Fetch top level items in batches
            batch_size = 100
            start = 0
            endpoint = (
                f"{self.api_base_url}/api/users/0/collections/{collection_key}/items/top"
                if collection_key
                else f"{self.api_base_url}/api/users/0/items/top"
            )

            while True:
                fetch_limit = min(batch_size, limit - len(results)) if limit else batch_size
                if fetch_limit <= 0:
                    break

                params: dict[str, Any] = {
                    "limit": fetch_limit,
                    "start": start,
                }
                if since_version:
                    params["since"] = since_version

                res = client.get(endpoint, params=params)
                res.raise_for_status()
                data = res.json()
                if not data:
                    break

                for entry in data:
                    item = self._parse_api_item(entry)
                    if item.item_type not in ("attachment", "note", "annotation"):
                        results.append(item)

                if len(data) < fetch_limit or (limit and len(results) >= limit):
                    break
                start += len(data)

            return results
        finally:
            client.close()

    def _parse_api_item(self, entry: dict[str, Any]) -> ZoteroItem:
        data = entry.get("data", {})
        meta = entry.get("meta", {})
        key = data.get("key", entry.get("key", ""))
        version = data.get("version", entry.get("version", 0))
        item_type = data.get("itemType", "journalArticle")

        date_val = data.get("date") or meta.get("parsedDate")
        year = None
        if date_val:
            m = re.search(r"\b(19\d\d|20\d\d)\b", str(date_val))
            if m:
                year = m.group(1)

        citekey = data.get("citationKey") or ""

        # Extract tags
        tags = [t.get("tag", "") for t in data.get("tags", []) if isinstance(t, dict) and t.get("tag")]

        # Extract collections
        collections = data.get("collections", [])

        abstract = ZoteroItem.clean_html(data.get("abstractNote"))

        return ZoteroItem(
            key=key,
            version=version,
            item_type=item_type,
            title=data.get("title", "Untitled").strip(),
            creators=data.get("creators", []),
            date=date_val,
            year=year,
            publication_title=data.get("publicationTitle"),
            publisher=data.get("publisher"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            doi=data.get("DOI"),
            url=data.get("url"),
            isbn=data.get("ISBN"),
            abstract=abstract,
            citekey=citekey,
            collections=collections,
            tags=tags,
            date_added=data.get("dateAdded", ""),
            date_modified=data.get("dateModified", ""),
        )

    def _attach_annotations_and_files(self, items: list[ZoteroItem]) -> None:
        """Fetch attachments and annotations via SQLite or API and attach to items."""
        # Using SQLite for attachment and annotation mapping is ultra-fast and avoids hundreds of HTTP queries
        if self.db_path.exists():
            self._attach_annotations_and_files_sqlite(items)
            return

        # Fallback to API if SQLite isn't local
        # If any item has missing citekey, query Better BibTeX JSON-RPC
        missing_citekeys = [it.key for it in items if not it.citekey]
        if missing_citekeys:
            try:
                with httpx.Client(timeout=10.0) as client:
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "item.citationkey",
                        "params": {"item_keys": missing_citekeys},
                        "id": 1,
                    }
                    res = client.post(f"{self.api_base_url}/better-bibtex/json-rpc", json=payload)
                    if res.status_code == 200:
                        keys_map = res.json().get("result", {})
                        for it in items:
                            if it.key in keys_map and keys_map[it.key]:
                                it.citekey = keys_map[it.key]
            except Exception:
                pass

        # Final fallback for citekey: generate author-year-title
        for it in items:
            if not it.citekey:
                it.citekey = self._generate_fallback_citekey(it)

    def _attach_annotations_and_files_sqlite(self, items: list[ZoteroItem]) -> None:
        if not self.db_path.exists() or not items:
            return

        items_by_key = {it.key: it for it in items}
        keys_placeholder = ",".join("?" for _ in items)
        keys_list = list(items_by_key.keys())

        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row

        try:
            # 1. Attach primary PDF paths
            query_attachments = f"""
                SELECT p.key as parent_key, att_item.key as att_key, att.path, att.contentType
                FROM itemAttachments att
                JOIN items att_item ON att.itemID = att_item.itemID
                JOIN items p ON att.parentItemID = p.itemID
                WHERE p.key IN ({keys_placeholder})
                  AND (att.contentType = 'application/pdf' OR att.path LIKE '%.pdf')
                ORDER BY att_item.itemID ASC
            """
            for r in conn.execute(query_attachments, keys_list).fetchall():
                parent_key = r["parent_key"]
                if parent_key in items_by_key and not items_by_key[parent_key].pdf_path:
                    raw_path = r["path"] or ""
                    if raw_path.startswith("storage:"):
                        filename = raw_path[len("storage:"):]
                        full_path = self.storage_dir / r["att_key"] / filename
                        if full_path.exists():
                            items_by_key[parent_key].pdf_path = str(full_path)
                    elif Path(raw_path).exists():
                        items_by_key[parent_key].pdf_path = str(Path(raw_path).resolve())

            # 2. Attach annotations
            query_annotations = f"""
                SELECT p.key as parent_key, a_item.key as annot_key, ia.text, ia.comment, ia.color, ia.pageLabel, ia.type
                FROM itemAnnotations ia
                JOIN items a_item ON ia.itemID = a_item.itemID
                JOIN itemAttachments att ON ia.parentItemID = att.itemID
                JOIN items p ON att.parentItemID = p.itemID
                WHERE p.key IN ({keys_placeholder})
                ORDER BY ia.sortIndex ASC
            """
            for r in conn.execute(query_annotations, keys_list).fetchall():
                parent_key = r["parent_key"]
                if parent_key in items_by_key:
                    items_by_key[parent_key].annotations.append(
                        Annotation(
                            key=r["annot_key"],
                            text=r["text"],
                            comment=r["comment"],
                            color=r["color"],
                            page=r["pageLabel"],
                            annotation_type=str(r["type"]),
                        )
                    )

            # 3. Ensure citekey exists
            for it in items:
                if not it.citekey:
                    it.citekey = self._generate_fallback_citekey(it)

        finally:
            conn.close()

    def _get_items_sqlite(
        self,
        limit: int | None = None,
        keys: list[str] | None = None,
        collection_key: str | None = None,
        since_version: int | None = None,
    ) -> list[ZoteroItem]:
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row

        try:
            sql = """
                SELECT i.itemID, i.key, i.version, it.typeName as itemType, i.dateAdded, i.dateModified
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
            """
            params: list[Any] = []

            if keys:
                sql += f" AND i.key IN ({','.join('?' for _ in keys)})"
                params.extend(keys)

            if collection_key:
                sql += """
                    AND i.itemID IN (
                        SELECT ci.itemID FROM collectionItems ci
                        JOIN collections c ON ci.collectionID = c.collectionID
                        WHERE c.key = ?
                    )
                """
                params.append(collection_key)

            if since_version:
                sql += " AND i.version > ?"
                params.append(since_version)

            sql += " ORDER BY i.dateModified DESC"

            if limit:
                sql += " LIMIT ?"
                params.append(limit)

            item_rows = conn.execute(sql, params).fetchall()
            items: list[ZoteroItem] = []

            for r in item_rows:
                item_id = r["itemID"]
                item_key = r["key"]

                # Get fields
                field_rows = conn.execute(
                    """
                    SELECT f.fieldName, idv.value
                    FROM itemData id
                    JOIN fields f ON id.fieldID = f.fieldID
                    JOIN itemDataValues idv ON id.valueID = idv.valueID
                    WHERE id.itemID = ?
                    """,
                    (item_id,),
                ).fetchall()
                fields = {fr["fieldName"]: fr["value"] for fr in field_rows}

                # Get creators
                creator_rows = conn.execute(
                    """
                    SELECT c.firstName, c.lastName, ct.creatorType
                    FROM itemCreators ic
                    JOIN creators c ON ic.creatorID = c.creatorID
                    JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
                    WHERE ic.itemID = ?
                    ORDER BY ic.orderIndex
                    """,
                    (item_id,),
                ).fetchall()
                creators = [
                    {
                        "firstName": cr["firstName"] or "",
                        "lastName": cr["lastName"] or "",
                        "creatorType": cr["creatorType"] or "author",
                    }
                    for cr in creator_rows
                ]

                # Get tags
                tag_rows = conn.execute(
                    """
                    SELECT t.name
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = ?
                    """,
                    (item_id,),
                ).fetchall()
                tags = [tr["name"] for tr in tag_rows]

                # Get collections
                coll_rows = conn.execute(
                    """
                    SELECT c.key
                    FROM collectionItems ci
                    JOIN collections c ON ci.collectionID = c.collectionID
                    WHERE ci.itemID = ?
                    """,
                    (item_id,),
                ).fetchall()
                collections = [cr["key"] for cr in coll_rows]

                date_val = fields.get("date")
                year = None
                if date_val:
                    m = re.search(r"\b(19\d\d|20\d\d)\b", str(date_val))
                    if m:
                        year = m.group(1)

                abstract = ZoteroItem.clean_html(fields.get("abstractNote"))

                items.append(
                    ZoteroItem(
                        key=item_key,
                        version=r["version"],
                        item_type=r["itemType"],
                        title=fields.get("title", "Untitled").strip(),
                        creators=creators,
                        date=date_val,
                        year=year,
                        publication_title=fields.get("publicationTitle"),
                        publisher=fields.get("publisher"),
                        volume=fields.get("volume"),
                        issue=fields.get("issue"),
                        pages=fields.get("pages"),
                        doi=fields.get("DOI"),
                        url=fields.get("url"),
                        isbn=fields.get("ISBN"),
                        abstract=abstract,
                        citekey="",
                        collections=collections,
                        tags=tags,
                        date_added=r["dateAdded"] or "",
                        date_modified=r["dateModified"] or "",
                    )
                )

            return items
        finally:
            conn.close()

    def _generate_fallback_citekey(self, item: ZoteroItem) -> str:
        """Generate Better BibTeX-style key: auth.lower + '-' + year + '-' + title words"""
        author_part = "anon"
        if item.authors:
            # First author last name
            first_author = item.creators[0].get("lastName") or item.authors[0].split()[-1]
            author_part = re.sub(r"[^\w]", "", first_author).lower()

        year_part = str(item.year) if item.year else "nodate"

        # First 3 words of title
        clean_title = re.sub(r"[^\w\s]", "", item.title).lower()
        title_words = [w for w in clean_title.split() if w not in ("a", "an", "the", "on", "in", "of")][:3]
        title_part = "-".join(title_words) if title_words else "paper"

        return f"{author_part}-{year_part}-{title_part}"

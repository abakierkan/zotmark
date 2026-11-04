# Zotmark (`zotmark`)

A fast, independent, and template-driven CLI tool that synchronizes your Zotero library and PDF annotations into Obsidian literature notes without relying on deprecated Obsidian plugins.

> [!TIP]
> For a comprehensive, step-by-step guide to configuring rules, routing categories, and writing Jinja2 templates, see the **[Configuration & Setup Guide](docs/CONFIGURATION_AND_SETUP.md)**.

---

## Features

- **Direct Live Connection:** Connects directly to local Zotero Desktop via its local Web API (`port 23119`) and Better BibTeX JSON-RPC (`/better-bibtex/json-rpc`).
- **Offline SQLite Fallback:** When Zotero Desktop is closed, safely reads `zotero.sqlite` directly in immutable read-only mode (`mode=ro&immutable=1`), avoiding database lock errors.
- **Category & Template Mapping:** Easily assign different templates and vault folders based on **collections** (e.g. `Qaidam solo-TnpB manuscript`), **item types** (e.g. `book` vs `journalArticle`), or tags.
- **Interactive Setup Wizard:** Run `zotmark init` to discover your Zotero categories and interactively configure your rules.
- **Jinja2 Templating:** Fully customizable templates with frontmatter, DOIs, authors, abstracts, and direct links to local PDF files (`file://...`).
- **PDF Annotation & Highlight Extraction:** Automatically pulls quotes, page numbers, color highlights, and comments from Zotero's PDF reader into callout blocks.
- **Non-Destructive Updates:** Automatically preserves any personal notes, synthesis, or backlinks written below the `<!-- USER_CONTENT_START -->` marker during future syncs.
- **Safe Dry-Run Mode:** Inspect exactly what files will be created or modified before touching disk.

---

## Quick Start

### 1. Inspect Your Library & Rules
```bash
zotmark list
```

### 2. Run the Interactive Setup Wizard (Optional)
If you want to reconfigure your categories, vault folders, or templates:
```bash
zotmark init
```

### 3. Preview Sync (Dry Run)
Preview notes that will be created or updated:
```bash
zotmark run --dry-run
```

### 4. Run Synchronization
```bash
# Sync all enabled categories
zotmark run

# Sync only the 5 most recently added items
zotmark run --recent 5

# Sync a specific item key
zotmark run --key JPAZLXQ2
```

### 5. Continuous Background Watcher
To periodically check for new items in Zotero (e.g., every 5 minutes):
```bash
zotmark watch --interval 300
```

---

## Configuration (`config.yaml`)

Your configuration lives in `config.yaml` and can be edited anytime:

```yaml
vault_path: "/home/xenologos/Koofr/obsidian"
default_output_dir: "02-Records/Literature"
file_name_format: "@{{ citekey }}"

zotero:
  api_url: "http://127.0.0.1:23119"
  db_path: "~/Zotero/zotero.sqlite"

categories:
  # Rule 1: Specific collection
  - name: "Qaidam Manuscript Collection"
    match:
      collection: "Qaidam solo-TnpB manuscript"
    output_dir: "02-Records/Literature/Qaidam"
    template: "templates/paper.md.j2"
    enabled: true

  # Rule 2: Books
  - name: "Books"
    match:
      item_type: "book"
    output_dir: "02-Records/Books"
    template: "templates/book.md.j2"
    enabled: true

  # Rule 3: Articles & Preprints
  - name: "Journal Articles & Preprints"
    match:
      item_type:
        - "journalArticle"
        - "preprint"
        - "conferencePaper"
    output_dir: "02-Records/Literature"
    template: "templates/paper.md.j2"
    enabled: true

  # Rule 4: Fallback
  - name: "All Other Items"
    output_dir: "02-Records/Literature"
    template: "templates/default.md.j2"
    enabled: true

sync:
  preserve_user_notes: true
  user_content_marker: "<!-- USER_CONTENT_START -->"
  include_annotations: true
  include_abstract: true
```

---

## Installation & Updates

To install or reinstall `zotmark` globally using `uv`:
```bash
cd /home/xenologos/Projects/zotmark
uv tool install . --editable --force
```

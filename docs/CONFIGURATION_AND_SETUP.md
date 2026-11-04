# Zotmark: Setup & Configuration Guide

This guide provides complete documentation for installing, configuring, and customizing `zotmark`, including detailed explanations of the configuration file, category routing rules, and Jinja2 template authoring for any Markdown-based note-taking application or literature scanning system.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Installation & Requirements](#2-installation--requirements)
3. [Quick Setup Wizard (`zotmark init`)](#3-quick-setup-wizard-zotmark-init)
4. [Configuration File (`config.yaml`) In-Depth](#4-configuration-file-configyaml-in-depth)
   - [Config File Discovery & Location](#config-file-discovery--location)
   - [Full Annotated Schema](#full-annotated-schema)
   - [Category Matching & Rule Precedence](#category-matching--rule-precedence)
   - [Common Item Types in Zotero](#common-item-types-in-zotero)
5. [Template Authoring Guide (Jinja2)](#5-template-authoring-guide-jinja2)
   - [Template Variables Reference](#template-variables-reference)
   - [Annotation & Highlight Objects](#annotation--highlight-objects)
   - [Writing Clean Callouts & Blockquotes](#writing-clean-callouts--blockquotes)
   - [Example: Research Paper Template](#example-research-paper-template)
   - [Example: Book Template](#example-book-template)
6. [Non-Destructive User Notes Preservation](#6-non-destructive-user-notes-preservation)
7. [Running & Automating Sync](#7-running--automating-sync)
   - [CLI Commands & Flags](#cli-commands--flags)
   - [Running as a Background Daemon (`watch`)](#running-as-a-background-daemon-watch)
   - [Setting Up a Systemd User Service](#setting-up-a-systemd-user-service)
8. [Troubleshooting & FAQ](#8-troubleshooting--faq)

---

## 1. Architecture Overview

`zotmark` is an independent bridge connecting your Zotero desktop library directly to your Markdown notes directory without depending on any specific application plugins or proprietary formats.

```
┌─────────────────────────────────┐
│     Zotero Desktop & Library    │
│  - Local Web API (port 23119)   │
│  - Better BibTeX JSON-RPC       │
│  - SQLite Fallback (mode=ro)    │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│         zotmark Engine          │
│  - Category & Collection Matcher│
│  - Jinja2 Template Renderer     │
│  - User Content Preserver       │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Markdown Notes Repository   │
│  - @citekey.md Markdown Notes   │
│  - YAML Frontmatter & Metadata  │
│  - PDF Highlights & Annotations │
│  - Preserved Personal Thoughts  │
└─────────────────────────────────┘
```

- **Dual-mode Data Engine:** Connects to `http://127.0.0.1:23119` when Zotero is running; automatically falls back to direct SQLite queries using URI mode `file:...zotero.sqlite?mode=ro&immutable=1` when Zotero is closed.
- **Citekey Integration:** Native support for Better BibTeX citekeys (e.g. `willingham-2008-critical-thinking-why`), with automatic fallback to standard `auth-year-title` generation.
- **Universal Markdown Output:** Generated notes use standard YAML frontmatter and GitHub-flavored Markdown, compatible with Obsidian, Logseq, SilverBullet, Foam, Zettlr, Neovim, or static site generators.

---

## 2. Installation & Requirements

### Requirements
- **Linux / macOS / Windows**
- **Python 3.12+**
- **uv** (recommended) or **pip**
- **Zotero 6 or 7** (with Better BibTeX installed for custom citekeys)

### Global Installation via `uv`
To make the `zotmark` command available anywhere in your terminal:

```bash
cd /home/xenologos/Projects/zotmark
uv tool install . --editable --force
```

Verify the installation:
```bash
zotmark --help
```

---

## 3. Quick Setup Wizard (`zotmark init`)

The fastest way to configure your sync rules is using the built-in interactive wizard:

```bash
zotmark init
```

The wizard will:
1. Test connection to your local Zotero instance.
2. Prompt for your **Markdown notes directory path** (e.g. `~/Notes`).
3. Prompt for your **default notes folder** inside the directory (e.g. `Literature`).
4. Prompt for your **note filename pattern** (e.g. `@{{ citekey }}`).
5. Query your Zotero library and list all discovered **Collections** and **Item Types**.
6. Ask which collections and item types to sync, and let you assign custom destination folders and templates to each.
7. Generate an editable `config.yaml` and copy starter templates to `templates/`.

---

## 4. Configuration File (`config.yaml`) In-Depth

### Config File Discovery & Location

`zotmark` searches for `config.yaml` in the following order:
1. Path provided explicitly via `--config-path <path>` or `-c <path>`.
2. Current working directory (`./config.yaml`).
3. User configuration directory (`~/.config/zotmark/config.yaml`).

---

### Full Annotated Schema

Here is a complete, annotated `config.yaml` explaining every option:

```yaml
# ==============================================================================
# Markdown Notes Directory Settings
# ==============================================================================

# Absolute or home-relative path to your Markdown notes root directory
notes_path: "~/Notes"

# Default folder inside your notes directory where notes will be written if a
# category rule does not specify a custom output_dir. (Relative to notes_path)
default_output_dir: "Literature"

# Note file naming pattern using Jinja2 syntax.
# Available variables: citekey, key, title, year, author
# Extension (.md) is added automatically if omitted.
# Examples:
#   "@{{ citekey }}"              -> @willingham-2008-critical-thinking-why.md
#   "{{ citekey }}"               -> willingham-2008-critical-thinking-why.md
#   "{{ year }} - {{ title }}"    -> 2008 - Critical Thinking Why Is It So Hard to Teach.md
file_name_format: "@{{ citekey }}"


# ==============================================================================
# Zotero Connection Settings
# ==============================================================================
zotero:
  # Base URL for Zotero's local HTTP API (running on port 23119 by default)
  api_url: "http://127.0.0.1:23119"

  # Path to your local Zotero SQLite database. Used automatically as a
  # zero-lock fallback when the Zotero desktop app is closed.
  db_path: "~/Zotero/zotero.sqlite"


# ==============================================================================
# Category Routing Rules
# ==============================================================================
# The rules list determines where each paper goes and which template formats it.
# Rules are evaluated from TOP to BOTTOM. The FIRST rule that matches an item
# is applied.
categories:
  # Rule Example 1: Match by Zotero Collection
  # Useful for project-specific bibliographies.
  - name: "Project Collection"
    match:
      collection: "My Research Project"
    output_dir: "Literature/Project"
    template: "templates/paper.md.j2"
    enabled: true

  # Rule Example 2: Match by Item Type (Books)
  - name: "Books"
    match:
      item_type: "book"
    output_dir: "Books"
    template: "templates/book.md.j2"
    enabled: true

  # Rule Example 3: Match multiple Item Types (Scientific Literature)
  - name: "Journal Articles & Preprints"
    match:
      item_type:
        - "journalArticle"
        - "preprint"
        - "conferencePaper"
    output_dir: "Literature"
    template: "templates/paper.md.j2"
    enabled: true

  # Rule Example 4: Catch-All Fallback
  # If an item does not match any previous rule, this rule catches it.
  - name: "All Other Items"
    output_dir: "Literature"
    template: "templates/default.md.j2"
    enabled: true


# ==============================================================================
# Sync Behavior Settings
# ==============================================================================
sync:
  # If true, any personal notes written below the user_content_marker will never
  # be overwritten or deleted during syncs.
  preserve_user_notes: true

  # Boundary string separating generated reference metadata from personal notes.
  user_content_marker: "<!-- USER_CONTENT_START -->"

  # Whether to extract and include PDF highlights and notes
  include_annotations: true

  # Whether to include the publication abstract
  include_abstract: true
```

---

### Category Matching & Rule Precedence

Rules under `categories` are evaluated sequentially:
1. **`match.collection`**: Matches if the item belongs to a Zotero collection whose name matches (case-insensitive substring or exact name).
2. **`match.item_type`**: Matches if the item's Zotero type matches a string (e.g. `"book"`) or any type in a list (e.g. `["journalArticle", "preprint"]`).
3. **Both specified**: If both `collection` and `item_type` are specified in a rule, the item must satisfy **both** conditions.
4. **Neither specified**: A rule without `match` criteria matches all items (use this as the last rule for your fallback template).
5. **`enabled: false`**: Disables the rule without deleting it.

---

### Common Item Types in Zotero

When writing `match.item_type`, use Zotero's internal type identifiers:

| Item Type Identifier | Common Name | Typical Template |
| :--- | :--- | :--- |
| `journalArticle` | Journal Article | `paper.md.j2` |
| `preprint` | Preprint (arXiv, bioRxiv) | `paper.md.j2` |
| `conferencePaper` | Conference Proceedings | `paper.md.j2` |
| `book` | Book | `book.md.j2` |
| `bookSection` | Book Chapter | `book.md.j2` |
| `thesis` | Master's Thesis / Ph.D. Dissertation | `paper.md.j2` |
| `report` | Technical Report / Whitepaper | `paper.md.j2` |
| `webpage` | Web Article / Blog Post | `default.md.j2` |
| `patent` | Patent | `default.md.j2` |

To see the exact counts of item types present in your own library:
```bash
zotmark list
```

---

## 5. Template Authoring Guide (Jinja2)

Templates use standard [Jinja2](https://jinja.palletsprojects.com/) syntax. You can edit existing templates in the `templates/` folder or create new ones.

### Template Variables Reference

The following variables are available inside any template:

| Variable | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `title` | `str` | Full title of the entry | `"Critical Thinking: Why Is It So Hard to Teach?"` |
| `citekey` | `str` | Better BibTeX citation key | `"willingham-2008-critical-thinking-why"` |
| `key` | `str` | 8-character Zotero item key | `"JPAZLXQ2"` |
| `authors` | `list[str]` | List of formatted author names | `["Daniel T. Willingham"]` |
| `authors_string` | `str` | Formatted author summary string | `"Willingham et al."` or `"Daniel T. Willingham"` |
| `year` | `str \| None`| 4-digit publication year | `"2008"` |
| `date` | `str \| None`| Raw publication date | `"2008-03-01"` |
| `publication_title` | `str \| None`| Journal or conference name | `"Arts Education Policy Review"` |
| `publisher` | `str \| None`| Publisher name (books/reports)| `"Routledge"` |
| `volume` | `str \| None`| Journal volume number | `"109"` |
| `issue` | `str \| None`| Journal issue number | `"4"` |
| `pages` | `str \| None`| Page range | `"21-32"` |
| `doi` | `str \| None`| Digital Object Identifier | `"10.3200/AEPR.109.4.21-32"` |
| `url` | `str \| None`| URL or web link | `"https://doi.org/10.3200/AEPR.109.4.21-32"` |
| `isbn` | `str \| None`| ISBN (books) | `"978-0-123456-78-9"` |
| `abstract` | `str \| None`| Cleaned abstract text (HTML stripped) | `"This review provides..."` |
| `tags` | `list[str]` | List of tags assigned in Zotero | `["crispr", "cas12", "endonuclease"]` |
| `collections` | `list[str]` | List of collection keys | `["JAMJ37AV"]` |
| `date_added` | `str` | ISO timestamp when added | `"2026-11-03T17:23:06Z"` |
| `date_modified` | `str` | ISO timestamp when modified | `"2026-11-03T17:23:07Z"` |
| `pdf_path` | `str \| None`| Absolute local file path to PDF | `"/home/user/Zotero/storage/.../paper.pdf"` |
| `annotations` | `list[Obj]` | List of extracted annotations | *(See below)* |
| `user_content_marker` | `str` | Marker for user note boundary | `"<!-- USER_CONTENT_START -->"` |

---

### Annotation & Highlight Objects

Each item in `annotations` has the following attributes:
- `a.text`: The text highlighted in the PDF.
- `a.comment`: The user comment or note attached to the highlight in Zotero.
- `a.page`: The page number or page label (e.g. `"192"`).
- `a.color`: Hex color of the highlight (e.g. `"#ffd400"`).
- `a.annotation_type`: Type of annotation (`"highlight"`, `"note"`, etc.).

---

### Writing Clean Callouts & Blockquotes

Callouts or blockquotes format cleanly when multiline text is prefixed with `> `. You can use Jinja2's `replace` filter:

```jinja2
{% if abstract %}
> [!abstract] Abstract
> {{ abstract | replace('\n', '\n> ') }}
{% endif %}
```

---

### Example: Research Paper Template

Located at [`templates/paper.md.j2`](file:///home/xenologos/Projects/zotmark/templates/paper.md.j2):

```jinja2
---
aliases:
  - "{{ title | replace('"', '\\"') }}"
  - "@{{ citekey }}"
tags:
  - "reference"
  - "literature"
{% for tag in tags %}  - "{{ tag }}"
{% endfor %}citekey: "{{ citekey }}"
title: "{{ title | replace('"', '\\"') }}"
authors:
{% for author in authors %}  - "{{ author }}"
{% endfor %}{% if year %}year: {{ year }}
{% endif %}{% if doi %}doi: "{{ doi }}"
{% endif %}{% if url %}url: "{{ url }}"
{% endif %}zotero_link: "zotero://select/items/{{ key }}"
date_added: "{{ date_added }}"
---

# {{ title }}

{% if abstract %}
> [!abstract] Abstract
> {{ abstract | replace('\n', '\n> ') }}
{% endif %}

## Reference Information
- **Authors:** {{ authors_string }}
- **Publication:** *{{ publication_title }}*{% if volume %} (Vol. {{ volume }}{% if issue %}, No. {{ issue }}{% endif %}){% endif %}
{% if pages %}- **Pages:** {{ pages }}
{% endif %}{% if year %}- **Year:** {{ year }}
{% endif %}{% if doi %}- **DOI:** [{{ doi }}](https://doi.org/{{ doi }})
{% endif %}- **Zotero:** [Open in Zotero](zotero://select/items/{{ key }})
{% if pdf_path %}- **PDF:** [Open PDF](file://{{ pdf_path }})
{% endif %}

{% if annotations %}
## Annotations & Highlights
{% for a in annotations %}
{% if a.text %}
> [!quote]{% if a.page %} (Page {{ a.page }}){% endif %}
> {{ a.text | replace('\n', '\n> ') }}
{% if a.comment %}
> - **Note:** {{ a.comment }}
{% endif %}
{% elif a.comment %}
- **Note{% if a.page %} (Page {{ a.page }}){% endif %}:** {{ a.comment }}
{% endif %}

{% endfor %}
{% endif %}

---
{{ user_content_marker }}
## Personal Notes & Synthesis

<!-- Anything below this line is preserved during sync -->
```

---

### Example: Book Template

Located at [`templates/book.md.j2`](file:///home/xenologos/Projects/zotmark/templates/book.md.j2):

```jinja2
---
aliases:
  - "{{ title | replace('"', '\\"') }}"
  - "@{{ citekey }}"
tags:
  - "reference"
  - "book"
{% for tag in tags %}  - "{{ tag }}"
{% endfor %}citekey: "{{ citekey }}"
title: "{{ title | replace('"', '\\"') }}"
authors:
{% for author in authors %}  - "{{ author }}"
{% endfor %}{% if year %}year: {{ year }}
{% endif %}{% if publisher %}publisher: "{{ publisher | replace('"', '\\"') }}"
{% endif %}{% if isbn %}isbn: "{{ isbn }}"
{% endif %}zotero_link: "zotero://select/items/{{ key }}"
date_added: "{{ date_added }}"
---

# {{ title }}

{% if abstract %}
> [!abstract] Overview
> {{ abstract | replace('\n', '\n> ') }}
{% endif %}

## Book Information
- **Authors:** {{ authors_string }}
{% if publisher %}- **Publisher:** {{ publisher }}
{% endif %}{% if year %}- **Year:** {{ year }}
{% endif %}{% if isbn %}- **ISBN:** {{ isbn }}
{% endif %}- **Zotero:** [Open in Zotero](zotero://select/items/{{ key }})
{% if pdf_path %}- **File:** [Open File](file://{{ pdf_path }})
{% endif %}

---
{{ user_content_marker }}
## Book Summary & Reflections

<!-- Anything below this line is preserved during sync -->
```

---

## 6. Non-Destructive User Notes Preservation

A common problem with reference sync tools is that modifying metadata in Zotero (e.g. fixing a title typo or adding a tag) overwrites the Markdown note, wiping out notes you took.

`zotmark` solves this cleanly:
1. Every note generated contains the boundary marker:
   ```markdown
   <!-- USER_CONTENT_START -->
   ```
2. When an item is updated, the tool reads the existing note on disk, separates the content above and below `<!-- USER_CONTENT_START -->`, updates the metadata and highlights in the top section, and **restores your personal notes verbatim** below the marker.
3. If an existing note on disk does not have the marker (e.g. an existing note you created manually), the tool safely places your existing text into a `## Preserved Notes` section rather than deleting it.

---

## 7. Running & Automating Sync

### CLI Commands & Flags

#### 1. Display Current Summary
Inspect your library and current active rules:
```bash
zotmark list
```

#### 2. Dry Run Preview
Test what would be created or updated without touching any files:
```bash
zotmark run --dry-run
```

#### 3. Run Sync
Synchronize all enabled items:
```bash
zotmark run
```

#### 4. Sync Only Recent Items
Sync only the $N$ most recently added items in Zotero:
```bash
zotmark run --recent 10
```

#### 5. Sync a Single Item
Sync one item by its 8-character Zotero key:
```bash
zotmark run --key JPAZLXQ2
```

#### 6. Force Overwrite Unchanged Notes
By default, notes whose content has not changed are skipped to avoid unnecessary file modification timestamps. To force re-rendering:
```bash
zotmark run --force
```

---

### Running as a Background Daemon (`watch`)

You can run `zotmark watch` to automatically check for newly added papers in Zotero and sync them:

```bash
# Check every 5 minutes (300 seconds)
zotmark watch --interval 300
```

---

### Setting Up a Systemd User Service

To run the sync watcher continuously in the background on Linux:

1. Create a user systemd service file at `~/.config/systemd/user/zotmark.service`:

```ini
[Unit]
Description=Zotmark Background Literature Sync Watcher
After=network.target

[Service]
Type=simple
ExecStart=/home/xenologos/.local/bin/zotmark watch --interval 300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
```

2. Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable --now zotmark.service
```

3. Check status and logs:
```bash
systemctl --user status zotmark.service
journalctl --user -u zotmark.service -f
```

---

## 8. Troubleshooting & FAQ

#### Q: How do I change where a collection is saved?
Open [`config.yaml`](file:///home/xenologos/Projects/zotmark/config.yaml), find the category rule matching that collection, and update `output_dir: "your/preferred/folder"`.

#### Q: Will this clash with Zotero Desktop when it's open?
**No.** When Zotero Desktop is open, the tool talks directly to the local HTTP server (`127.0.0.1:23119`). When Zotero Desktop is closed, the tool connects to `zotero.sqlite` with SQLite parameters `mode=ro&immutable=1`, which bypasses locks.

#### Q: What happens if Better BibTeX is not installed?
The tool automatically falls back to generating clean standard citekeys matching the formula:
`firstauthor-year-first3wordsoftitle` (e.g. `willingham-2008-critical-thinking-why`).

#### Q: How do I exclude certain collections from being synced?
In `config.yaml`, either set `enabled: false` on that category rule, or simply do not include a rule for it if you don't have a catch-all fallback rule enabled.

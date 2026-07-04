---
name: my-skill
description: Expert guidelines and best practices for identifying, categorizing, and organizing unstructured files into elegant, descriptive directories.
---

# File Categorization and Organization Skill

Use this skill to determine the most logical, elegant, and professional way to group files and name their target folders.

## 1. Elegant Directory Naming Principles

Never use generic, boring folder names. Generate directory names that immediately communicate the purpose and subject of the files.

*   **AVOID:** `scripts`, `code`, `python`, `files`, `docs`, `images`, `pdfs`
*   **PREFER:**
    *   `Core Python Helper Scripts` or `Workflow Automation Code` (instead of `python` / `scripts`)
    *   `Financial Reports & Q3 Spreadsheets` or `Marketing Project Briefs` (instead of `docs` / `xlsx`)
    *   `UI Vector Illustrations` or `App Graphics & Screenshots` (instead of `images`)
    *   `Database Migration Scripts` or `SQL Schema Definitions` (instead of `sql`)

## 2. File Grouping Rules

When reviewing files, categorize them by blending their **Format Group**, **Subject Matter**, and **Context clues** (from their content snippets).

### A. Source Code and Configurations
*   **Programming Source Code:** Group files of the same programming language together, but separate them if they serve completely different purposes (e.g., separate `frontend_components` from `database_migrations`).
*   **Project Configs:** Files like `.json`, `.yaml`, `.toml`, `Dockerfile`, and dependency files belong in a folder named `Project Setup & Configurations` or `Build & Environment Settings`.

### B. Documents and Data
*   **Spreadsheets & Data:** Group CSVs, Excel, and JSON data files under `Data Inputs & Raw Datasets` or `Financial & Analytical Spreadsheets`.
*   **Documentation & Markdown:** Put guides, READMEs, plans, and instructions under `Project Documentation & Guides` or `System Architecture Documents`.

### C. Media and Assets
*   **Media Assets:** Group `.png`, `.jpg`, `.svg`, and `.gif` together, but identify if they are user interface elements (`UI Design Assets`), illustrations, or raw media (`Product Photos & Icons`).

## 3. Ambiguity Resolution

If a file could fit into multiple folders:
1.  Check the text snippet for imports or keywords that indicate its primary function.
2.  Default to grouping it with the files it interacts with (e.g., group a `.json` configuration file with the python scripts that parse it if they are highly related, or keep it in `Configurations`).

## 4. Pre-Existing Folders Rule

If files are already grouped inside a subfolder:
1.  **Do not break up or touch the files individually.**
2.  Treat and categorize the **entire folder as a single unit** rather than individual separate files.
3.  Keep the internal structure of that pre-existing folder completely intact.

## 5. Non-Destructive Integrity Rule

You must **NEVER modify, touch, write to, edit, or overwrite the contents of any user file.**
1.  All operations must be completely non-destructive (read-only for analysis).
2.  Original file structures and byte contents must remain 100% untouched.
3.  Your task is strictly limited to categorization and folder structuring; file content changes are completely prohibited.



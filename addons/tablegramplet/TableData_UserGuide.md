# TableData Gramplet — User Guide

TableData is a Gramps addon that lets you attach arbitrary structured data to
any object in your family tree — a person, family, event, place, source,
citation, repository or media item.  You define your own columns, choose a
data type for each one, and enter as many rows as you like.  Each object in
your tree gets its own independent set of rows, while the column layout is
shared across all objects of the same type.

---

## Table of Contents

1. [Installation](#installation)
2. [Adding the gramplet to a view](#adding-the-gramplet-to-a-view)
3. [Interface overview](#interface-overview)
4. [Tables](#tables)
   - [Adding a table](#adding-a-table)
   - [Renaming a table](#renaming-a-table)
   - [Deleting a table](#deleting-a-table)
5. [Columns](#columns)
   - [Column types](#column-types)
   - [Adding a column](#adding-a-column)
   - [Editing a column](#editing-a-column)
   - [Reordering columns](#reordering-columns)
   - [Deleting a column](#deleting-a-column)
6. [Rows](#rows)
   - [Adding a row](#adding-a-row)
   - [Editing a row](#editing-a-row)
   - [Deleting a row](#deleting-a-row)
   - [Sorting rows](#sorting-rows)
7. [URL cells](#url-cells)
8. [Import and export](#import-and-export)
   - [Exporting to CSV or ODS](#exporting-to-csv-or-ods)
   - [Importing from CSV or ODS](#importing-from-csv-or-ods)
   - [CSV format details](#csv-format-details)
   - [ODS support](#ods-support)
9. [Data storage](#data-storage)
10. [Tips and examples](#tips-and-examples)

---

## Installation

1. Download or copy the `TableData/` folder containing these files:

   ```
   TableData/
   ├── tabledata_base.py
   ├── tabledata_person.py
   ├── tabledata_family.py
   ├── tabledata_event.py
   ├── tabledata_place.py
   ├── tabledata_source.py
   ├── tabledata_citation.py
   ├── tabledata_repository.py
   ├── tabledata_media.py
   └── tabledata.gpr.py
   ```

2. Place the folder in your Gramps user plugins directory:

   | Platform     | Path |
   |--------------|------|
   | Linux/macOS  | `~/.gramps/gramps52/plugins/TableData/` |
   | Windows      | `%APPDATA%\gramps\gramps52\plugins\TableData\` |

3. Restart Gramps.

### Optional: ODS support

To enable import and export of ODS (OpenDocument Spreadsheet) files, install
the `odfpy` package:

```
pip install odfpy
```

CSV import and export works without any additional packages.

---

## Adding the gramplet to a view

Each Gramps object type has its own independent TableData gramplet:

| Gramplet name         | Shows in view    |
|-----------------------|------------------|
| Person Table Data     | People view      |
| Family Table Data     | Families view    |
| Event Table Data      | Events view      |
| Place Table Data      | Places view      |
| Source Table Data     | Sources view     |
| Citation Table Data   | Citations view   |
| Repository Table Data | Repositories view|
| Media Table Data      | Media view       |

To add a gramplet:

1. Open the view where you want the gramplet (e.g. the People view).
2. Click the **+** button at the right edge of the bottombar or sidebar.
3. Find the appropriate **Table Data** gramplet in the list and click **Add**.

The gramplet can also be detached into a floating window via its properties
menu (the small triangle in the gramplet title bar).

---

## Interface overview

```
┌─────────────────────────────────────────────────────────┐
│ [➕ table] [✏️ table] [➖ table]                          │  ← table toolbar
├─────────────────────────────────────────────────────────┤
│  Measurements  │  External Links  │  Notes  │           │  ← tabs (one per table)
├─────────────────────────────────────────────────────────┤
│ [➕col][✏️col][➖col] [◀] [▶] │ [➕row][✏️row][➖row] │ 💾 📂 │  ← row/col toolbar
├──────────────┬──────────────┬──────────────────────────┤
│  Date        │  Value       │  Notes                   │  ← column headers (click to sort)
├──────────────┼──────────────┼──────────────────────────┤
│  1923-04-12  │  72.5        │  Measured at clinic      │
│  1951-09-01  │  68.0        │                          │
└──────────────┴──────────────┴──────────────────────────┘
```

The **table toolbar** at the top manages tables (tabs).
The **column/row toolbar** inside each tab manages the schema and data for that table.

---

## Tables

A table is an independent tab with its own set of columns and its own rows
per object.  You can have as many tables as you like within one gramplet — for
example one table for physical measurements, another for external links, and
another for research notes.

The **column schema** of a table (its column names and types) is **shared**
across all objects of the same type — if you add a "Height" column to the
Person Table Data gramplet, every person will have that column available.
The **row data** is **per object** — each person stores their own rows
independently.

### Adding a table

Click **➕** in the top toolbar.  Enter a name for the new table and click
**OK**.  The new table appears as a tab at the right end.

### Renaming a table

Switch to the tab you want to rename.  Click **✏️** in the top toolbar.
Edit the name and click **OK**.

### Deleting a table

Switch to the tab you want to delete.  Click **➖** in the top toolbar.
Confirm the deletion in the dialog that appears.

> **Warning:** Deleting a table permanently removes the table, all its
> columns, and all row data for every object in the tree.  This cannot
> be undone.

---

## Columns

### Column types

Each column has one of three types:

| Type   | Accepted values | Notes |
|--------|----------------|-------|
| **String** | Any text | Default type |
| **Number** | Integers or decimals (e.g. `42`, `3.14`, `-0.5`) | Validated on entry; invalid values are rejected |
| **URL** | Any text, typically a web address | Displayed as a clickable blue link; see [URL cells](#url-cells) |

### Adding a column

Click **➕** (first button in the column/row toolbar).  Enter a column name,
choose a type, and click **OK**.  The column is appended to the right of
existing columns.

> Column names and types are shared across all objects of the same type
> within this table.  Changing the schema affects every object.

### Editing a column

Click any cell in the column you want to edit to focus it, then click **✏️**
(third button).  You can change the column name and/or its type.

> Changing a column's type does not validate or convert existing cell values.
> For example, if you change a String column to Number, existing non-numeric
> values remain stored and will be displayed as-is, but new values will be
> validated.

### Reordering columns

Click any cell in the column you want to move to focus it, then use:

- **◀** — move the column one position to the left
- **▶** — move the column one position to the right

The column header and all its data move together.  The cursor follows the
column to its new position, so you can press the button repeatedly to move a
column several positions.

### Deleting a column

Click any cell in the column you want to delete to focus it, then click
**➖** (second button).  Confirm in the dialog.

> **Warning:** Deleting a column removes that column's data for **all**
> objects of this type in the tree.  This cannot be undone.

---

## Rows

Row data is per-object.  When you select a different person (or family, event,
etc.) in the main Gramps view, the gramplet automatically reloads and shows
only that object's rows.

### Adding a row

An object must be selected in the main view first.  Click **➕** (fourth
button, after the separator).  A dialog appears with one entry field per
column.  Fill in the values and click **OK**.

- Number fields reject non-numeric input and show an error.
- URL fields show a placeholder hint (`https://…`).
- Any field may be left blank.

### Editing a row

Select the row in the table by clicking it, then click **✏️** (sixth button).
The same dialog as for adding appears, pre-filled with the current values.
Edit and click **OK**.

### Deleting a row

Select the row in the table, then click **➖** (fifth button).  The row is
deleted immediately without a confirmation dialog.

### Sorting rows

Click any column header to sort all rows by that column.  Click again to
reverse the sort order.  The column header shows a **▲** or **▼** arrow
indicating the current sort direction.

Sort behaviour by type:

| Type   | Sort order |
|--------|-----------|
| String | Alphabetical, case-insensitive |
| Number | Numeric ascending/descending; blank cells sort last |
| URL    | Alphabetical, case-insensitive |

Sorting is a view-only operation — the stored row order in the database is
not changed.

---

## URL cells

Cells in a **URL** column are displayed in blue with an underline.  Clicking
a URL cell opens the address in your default web browser using the system's
standard URL handler (`xdg-open` on Linux, `open` on macOS, the default
browser on Windows).

URLs do not need to start with `https://` — any string is accepted and will
be passed to the browser as-is.  Common formats include:

- `https://www.ancestry.com/…`
- `http://familysearch.org/…`
- `file:///home/user/scans/birth_certificate.pdf`

---

## Import and export

Import and export operate on the **current object's rows** only — they do not
batch-export data for all persons or all families at once.

The export (💾) and import (📂) buttons are the last two buttons in the
column/row toolbar.

### Exporting to CSV or ODS

1. Click **💾** (export button).
2. Choose a save location and filename.
3. Select the file format using the filter dropdown, or type the extension
   directly (`.csv` or `.ods`).
4. Click **Save**.

The exported file contains one header row with the column names, followed by
one data row per stored row for the currently selected object.

If no extension is given, `.csv` is used automatically.

### Importing from CSV or ODS

1. Select the object you want to import data into.
2. Click **📂** (import button).
3. Choose the file to import.
4. Review the confirmation dialog showing how many rows will be imported.
5. Click **Yes** to proceed.

**Schema reconciliation during import:**

- The first row of the file is treated as the header row containing column names.
- Each header name is matched to existing columns **case-insensitively**.
- If a header name matches an existing column, that column is used.
- If a header name does not match any column, a new **String** column is
  created automatically.
- If the table has no columns at all, all columns are created from the header.

**Existing rows are preserved.**  Imported rows are always appended; no
existing rows are modified or deleted.

**Number validation:**  Rows containing invalid values in Number columns are
skipped.  A summary at the end reports how many rows were imported and how
many were skipped.

### CSV format details

- Encoding: UTF-8 (UTF-8 with BOM is also accepted on import).
- Delimiter: comma (`,`).
- First row: column headers.
- Values containing commas or newlines are automatically quoted.
- Produced by any standard spreadsheet application (LibreOffice Calc,
  Microsoft Excel, Google Sheets) when saving as CSV.

### ODS support

ODS (OpenDocument Spreadsheet) is the native format of LibreOffice Calc.

**Requirement:** the `odfpy` Python package must be installed.

```bash
pip install odfpy
```

When exporting to ODS, the sheet name is set to the table's name.
When importing from ODS, only the first sheet in the file is read.

If `odfpy` is not installed:
- The ODS filter option does not appear in the file dialog.
- If you manually type `.ods` as the filename extension when exporting,
  the addon will warn you and fall back to CSV.

---

## Data storage

All data is stored in a single SQLite database file located inside your
family tree folder:

```
<family-tree-folder>/tabledata.db
```

This file is created automatically the first time the addon runs.  It is
separate from the main Gramps database and is not managed by Gramps — it will
not be included in Gramps backups unless you back up the tree folder manually.

> **Recommendation:** include `tabledata.db` in your regular backup routine
> alongside the Gramps database files.

The database has three tables:

| Table     | Contents |
|-----------|---------|
| `tables`  | One row per named table (tab) per object type |
| `columns` | Column definitions (name, type) per table |
| `rows`    | Cell values, keyed by table + object handle + row position + column position |

The column schema is **shared** across all objects of the same type.
The row data is **per-object**, keyed by the Gramps internal handle.

If the family tree is renamed or moved, the `tabledata.db` file travels with
it as long as it stays inside the tree folder.

---

## Tips and examples

**Recording physical measurements for persons**

Create a table called "Measurements" with columns:
- `Date` (String)
- `Height cm` (Number)
- `Weight kg` (Number)
- `Source` (String)

Each person then stores their own height/weight history independently.

**Tracking DNA test results**

Create a table called "DNA Tests" on the Person gramplet with columns:
- `Company` (String)
- `Kit number` (String)
- `Test date` (String)
- `Result URL` (URL)

**Linking to external records**

Create a table called "External Links" with columns:
- `Site` (String)
- `Description` (String)
- `URL` (URL)

Click any URL cell to open the link directly in your browser.

**Importing a spreadsheet of research notes**

Prepare a CSV with headers matching your column names, then use the import
button to append rows to the currently selected person.  Unknown headers
automatically become new columns.

**Keeping multiple independent tables per object**

Use separate tabs for logically unrelated data — for example one tab for
vital statistics, another for occupational history, and a third for
documentary evidence — rather than cramming everything into one wide table.
Each tab is completely independent and can have its own column schema.

# Accreditation Hub

A shared Northwest University workspace for accreditation cycles, editable standards and criteria, Google Drive evidence links, and semester reviews. Python/SQLite provides shared storage; Microsoft Entra provides university sign-in. The interface uses plain HTML/CSS/JavaScript, with no Node build required.

> **Prototype — not approved for production use.** University authentication configuration, approved hosting, upload scanning, backup operations, and security/browser review are required before using private university records. This repository contains no runtime database or credentials.

## Continue developing locally

Run `.venv/bin/python -B run_local.py`, open http://127.0.0.1:8000/login, and enter the password from `.local-dev-password` in this folder. This explicit localhost-only mode gives you development admin access to your saved workspace while university IT setup is pending. Production startup still requires Microsoft sign-in.

## Sign-in setup and running the app

See **[SECURITY_SETUP.md](SECURITY_SETUP.md)** for the IT registration checklist, environment variables, deployment, and verification. The initial administrator is configured using `ENTRA_ADMIN_EMAIL`, paired with their Microsoft Entra user Object ID supplied by IT. Real university sign-in cannot work until the app registration and credentials are configured.

Use Python 3.12+ with OpenSSL:

```sh
cd '/path/to/accreditation-hub'
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Without Entra configuration, http://127.0.0.1:8000 shows the login/setup page and **blocks access to accreditation data**. There is no default password or shared-password bypass. All project files and the SQLite database are kept in this folder. The service must be deployed behind university-managed HTTPS with persistent storage; see the setup guide before publishing.

## Permissions and deletion

- **Staff:** read cycles, edit existing records and checklists, upload evidence and updated file versions, attach evidence to empty criterion fields, export data.
- **Administrators:** staff permissions plus add/delete cycles, standards, criteria and tasks; manage the owner list; add/replace/delete evidence links; restore backups; manage approved users and roles; restore or permanently delete archived records.
- **Archives:** use the link in the account bar. Delete a cycle using the trash icon in its workspace footer; delete a standard, criterion, review task, or evidence link from its edit dialog. Deleted records remain recoverable until explicitly purged. Restoration refuses collisions.
- **People & access:** admins enter the approved university email, Microsoft Entra user Object ID, and role. This grants tracker access; it does not create a university account or send an email. Delete access immediately revokes that person's local sessions and archives their membership.

Only approved accounts in the configured university tenant, with an exact `@northwestu.edu` directory username, can sign in. Admin controls are enforced on the server, not just hidden in the interface. Linked Google Drive documents are never deleted by tracker operations, even when archives are permanently deleted.

## Staff guide

1. Click **Edit project** to change the project title and introduction.
2. Review the starter standard headings and replace each placeholder criterion with your institution's approved criterion. Use **Edit standard**, **Add standard**, and **Add criterion**. Criteria accept a short code and title plus detailed requirements in notes. No code changes are needed.
3. Use the inline owner, status, and evidence dropdowns to update a criterion immediately. Choose **＋ Add owner…** to add a name to the shared owner list. Click any criterion to edit its other details and paste an HTTPS `docs.google.com` or `drive.google.com` link. Documents stay in Google Drive: staff must manage their permissions there. The tracker does not check Drive access or sync document contents.
4. Filter by status, or search for a title, owner, code, or note. The Standards & Criteria page and its editor do not display reporting years. Existing year values are retained in storage and exports; semester reviews still have year selectors. New criteria use the selected cycle’s start year internally.
5. In **Semester reviews**, choose Spring/Fall and a year, then **Create semester tasks**. This creates one task per standard for that period without duplicates. Assign owners, due dates, and notes with **Edit task**. Check criteria as they are reviewed. A task is complete only when it has criteria and all are checked. Added criteria automatically join existing checklists; deleting criteria removes their checklist entries. Review checks are independent of criterion workflow status. Tasks are generated on demand for Spring/Fall in each year of the selected cycle.
6. Use **Submission overview** to identify missing owners, links, and incomplete work. **Print / Save PDF** produces a team summary, including document URLs and notes. **Export criteria CSV** downloads the full criteria register regardless of active filters. CSV is an export, not an import format.
7. **Download backup** exports the entire project, including reviews. **Restore backup** validates and replaces the shared project after confirmation. Admins can restore backups; removed records are captured in Archives. Download a backup before replacing existing work. To duplicate a criterion, add another and copy its fields; there is no duplicate button.

Changes save explicitly from each form; checklist changes save immediately. Other staff see the latest data when they reload. If someone saved since your last load, your save is rejected rather than overwriting their work. Copy your pending form text before reloading (the downloadable backup contains your last loaded/saved project, not unsaved form text), then reapply changes. A failed save stays open for retry. There is no offline editing.

## Backups and recovery

Download a JSON backup regularly and retain it according to school policy. Store downloaded exports in this project folder if you want to keep all project artifacts together. For a full database copy, stop the server and copy `data/tracker.sqlite3` into a dated backup inside `data/`, then restart. To recover, stop the server and replace the database file with the saved copy, or use **Restore backup** for JSON. Set up recurring backups on the hosting server before production use. Do not commit the database, exports containing school data, or passwords to a public repository.

## Scope and official framework

The seven starter headings reflect ACBSP's published framework, but each seeded criterion is deliberately a **placeholder**, not an official requirement. Confirm the applicable program, standard version, numbering, and 2031 requirements before relying on this tracker. Source: [ACBSP standards](https://acbsp.org/page/accreditation-standards) and [official documents and resources](https://acbsp.org/page/accreditation-documents), consulted September 20, 2026. The submission overview checks administrative completeness; it does not certify compliance or produce the official self-study submission. Evidence files can be uploaded privately through the Evidence library; existing Google Drive living-document links remain supported.

## Verification and customization

```sh
.venv/bin/python -B -m unittest discover -s tests -v
node --check static/app.js
```

The Python tests cover migration, cycle isolation, stale-save conflicts, validation, session expiry, CSRF, server-side roles, identity rejection, and archive/restore/purge behavior. Microsoft tenant sign-in is mocked; real sign-in must be verified with IT. Run `node tests/check_cycle_ui.js` to check cycle-specific browser logic. Node is only used for the optional JavaScript syntax check. UI styles are in `static/style.css`; browser behavior in `static/app.js`; validation and defaults in `server.py`. Editing seed defaults affects new databases only. Staff should normally customize the live project in the UI.

## Accreditation hub and university logo

The home page (`/`) is the cycle selector. The original **2021–2031** card opens the existing ACBSP 2031 project at `/cycles/2021-2031`; additional cycles open at their own year-based URLs. The logo links back home. Existing records keep their years; semester-review choices now span the selected cycle’s full year range.

The official logo is stored locally at `static/nu-logo-reversed.svg`, sourced from https://www.northwestu.edu/assets/svgs/nu-logo-reversed.svg. Landing-page styles are in `static/home.css`. No visitor requests to the university website are needed to load the logo.

Each cycle now has a separate project record and revision in SQLite. The landing page lists saved cycles dynamically, and each workspace uses its own API route. The landing page and tracker both require university sign-in. Each session has a server-checked staff or administrator role.

## Eagle opening sequence

The eagle flies left to right for about four seconds. A translucent backdrop blur clears from left to right in proportion to the eagle’s horizontal position: when it crosses 10% of the viewport, the left 10% is visible. The eagle exits the right edge and the overlay is removed. It does not travel around the logo or remain anywhere on the site. No perched eagle is rendered or loaded.

Skip, Escape, reduced-motion settings, asset-loading failures, and tab visibility changes bypass the intro. It uses `static/eagle-original-flight.png` with continuous 2D wing deformation. Previous flight/perching assets are retained locally but are not used. The generated artwork's prompt is saved in `tools/eagle-generation-prompt.txt`.

## Add an accreditation cycle

As an administrator, on the landing page choose **Add accreditation cycle**. Enter the cycle name, start/end years, coordinator, optional target submission date, and optional description. Choose the standard starter framework (seven standards and 30 criteria), copy another cycle’s framework, or choose **Build your own framework (start empty)**. The empty option creates no standards or criteria; admins build them using **Add standard** and **Add criterion** in the new workspace. Only standard names and criterion codes/titles carry over; owners, links, notes, evidence/workflow status, and semester tasks are reset. The new workspace opens immediately after creation.

The name, description, coordinator, and submission date remain editable through **Edit project**. Years identify the cycle and are fixed after creation; one cycle is allowed per start/end-year pair. Cycles may overlap in years. Labels such as Current/Upcoming/Past reflect the visitor’s current calendar year, not accreditation approval.

The original project migrates automatically into the `cycles` table on first startup after this update. Its standards, criteria, links, notes, and reviews are preserved; the old `project` row is retained as a legacy snapshot. `/api/project` remains an alias for the original 2021–2031 cycle; new clients use `/api/cycles/{start}-{end}/project`. Existing stale-save protection operates independently per cycle. Only admins can create or archive cycles; signed-in staff can update existing work.

CSV and JSON exports apply to the open cycle and use its years in the filename. JSON backups identify their cycle and cannot be restored over a different year range. To back up **all cycles**, back up the entire SQLite database. Use the cycle card’s Delete button to move a complete cycle to Archives.

## Evidence library

Open **Evidence** in a cycle’s workspace, using **Upload evidence** in that library. Signed-in staff and admins can upload PDF, DOCX, XLSX, PPTX, UTF-8 TXT/CSV, PNG, and JPG files, up to **10 MB each**. The initial storage cap is **1 GB** across all retained versions. Files are stored privately in this project’s SQLite database; there is no Google Drive connection or external upload. On a hosted installation, the database must live on persistent server storage.

Choose **Copy link**, then paste it into a criterion’s **Evidence link** column (or its edit form). The original **Living document** column remains separate. Staff can attach evidence to an empty field; admins can replace or remove an existing reference. External HTTPS document links can also be entered manually. Portal links are checked against the selected cycle.

Open an evidence link to download its current file or an older version. Edit a downloaded document using its appropriate application, then choose **Upload updated version** on the document page. The stable evidence link stays the same. This is not an online Word/PDF editor. Recipients must sign in; a copied link grants no additional access. Localhost links work only on the development computer; shared links become usable by colleagues when the app is hosted at its shared URL. Internally, portal references are stored as relative paths to allow a host change.

Only admins can delete evidence records. Records go to Archives and can be restored after their parent cycle is restored. Permanent tracker deletion retains file bytes and version metadata; inactive document downloads require admin access. Permanently deleting a cycle retires its active evidence records so a newly created cycle with the same years starts clean. No cloud files are ever altered.

Back up the **entire SQLite database** to preserve uploads, versions, archives, and accounts. Per-cycle JSON backups and CSV exports include references, **not file bytes**. Retained files continue to count toward storage usage. IT must manage retention and quota increases separately; there is no automatic file erasure.

## Custom workspace tasks

Admins can click **＋** beside Workspace to add a named section and choose Text, Document, Media, Pictures, Charts, or a custom category. Categories organize the work; they do not enable a separate media editor or chart-building tool. Each section saves draft text/notes and a portal evidence or HTTPS resource link. Use the Evidence library to upload supported documents, then paste its copied link into the section. Media may be linked from an HTTPS source. Staff can edit existing section content.

Right-click a custom sidebar section (or select its **⋯** button) to edit its name/category or delete it. Shift+F10 opens the same menu from the keyboard. Only admins can add/delete or change names/categories. Deletion moves the section and all its text/link data into Archives. Restoration checks for ID/name conflicts; underlying documents remain untouched. Custom tasks belong to one cycle and are included in that cycle’s JSON backup, but framework templates do not copy them into new cycles.

### Chart workspaces
Use **+** beside Workspace, enter a name, and select **Charts**. The chart builder provides 22 chart types, an editable data table, spreadsheet paste, titles, axis titles, colors, font choices, legends, grid lines, and data labels. Special chart types explain their data format below the preview. Sample data is not saved until you choose **Save chart**. Save before navigating away. PNG/SVG and data CSV downloads are available. This is a 2D chart builder, not a complete Microsoft Word chart implementation (3D surfaces and geographic maps are not included).

Charts are saved with the task in shared storage and included in backups and archive restoration. Chart rendering uses locally bundled Apache ECharts 5.6.0; no chart data goes to an external chart service. Its license is in `static/ECHARTS-LICENSE.txt`.

Administrators can right-click a sidebar section (or focus it and press Shift+F10) to open its menu. Removing a built-in section hides it from the sidebar and archives the section entry; its underlying records and uploaded files remain saved. Restore the section from **Archives**. Custom task deletion archives its complete contents, including its chart.

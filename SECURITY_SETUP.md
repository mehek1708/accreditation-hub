# University sign-in and deployment setup

The tracker now requires Microsoft Entra sign-in. It **fails closed**: without configuration, only the login page and its public styling/logo are accessible. The normal server has no shared-password fallback, email-only signup, or default administrator password. Explicit localhost development is described below. Existing accreditation data remains in SQLite.

## University IT: register the application

1. In Northwest University's Microsoft Entra tenant, create an app registration for **accounts in this organizational directory only**. Do not use `common`, `organizations`, consumer accounts, or a multi-tenant registration.
2. Add a **Web** redirect URI: `https://YOUR-TRACKER-HOST/auth/callback`. For local verification, separately register the exact localhost origin plus `/auth/callback` and use that same origin in `TRACKER_ORIGIN`.
3. Configure delegated Microsoft Graph **User.Read** permission and grant consent according to university policy. The server reads only the signed-in user's `id`, `userPrincipalName`, and `userType`. No Google Drive or Microsoft file access permissions are needed. The MSAL authorization-code flow handles state, nonce, and PKCE; tokens stay server-side and are discarded after identity verification.
4. Create a client credential, place its **value** in the university secret manager, and set an expiry/rotation reminder. Never put it in source control, a URL, client JavaScript, or chat.
5. Configure the Enterprise Application to require user assignment. Assign approved staff. Require MFA using university Conditional Access (or the university's applicable security policies). Password strength, password reset, sign-in risk controls, and MFA are administered by Microsoft/IT, not by this tracker.
6. Supply the university **Directory (tenant) ID**, application's **Application (client) ID**, and the **user Object ID** for `admin@northwestu.edu`. The user Object ID is under Entra → Users → that person → Overview; it is not the application Object ID. Set the approved initial administrator email through `ENTRA_ADMIN_EMAIL`.
7. Set these server environment variables (names also in `.env.example`):
   - `ENTRA_TENANT_ID`
   - `ENTRA_CLIENT_ID`
   - `ENTRA_CLIENT_SECRET`
   - `ENTRA_ADMIN_OBJECT_ID`
   - `TRACKER_ORIGIN` — exact HTTPS origin, no trailing path; e.g. `https://accreditation.northwestu.edu`
8. Use supported **Python 3.12+ with OpenSSL** for real Microsoft sign-in. Apple's bundled Python 3.9/LibreSSL is unsuitable for the installed HTTP library; it was used only for offline/local integration checks. The provided Dockerfile uses Python 3.12.

The first configured startup creates the initial admin once. Later role changes are database-backed; restarting does not re-promote removed admins. Only directory **Member** accounts with an exact `@northwestu.edu` UPN, matching the approved immutable Object ID and expected email, can enter. Guests, personal Microsoft accounts, other tenants, suffix lookalikes, and unapproved university members are rejected. If university UPNs differ from email addresses, IT must resolve that before launch; the app deliberately does not relax the domain check.

## Run and verify

```sh
cd '/path/to/accreditation-hub'
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Inject the variables above through the hosting environment/secret manager.
.venv/bin/python server.py
```

Open the configured origin. The example file is documentation; the app does **not** automatically load `.env`. For a local-only setup page without credentials, `.venv/bin/python server.py` serves http://127.0.0.1:8000/login and keeps data locked.

Before granting production access, IT must complete a real sign-in check:

- Confirm the initial administrator reaches the hub; verify MFA enforcement in Entra.
- Add an approved staff account in **People & access** using their directory Object ID. Confirm it can update existing criteria but receives 403 for administrative operations.
- Confirm an unapproved university member, guest, and outside-domain account cannot enter.
- Verify logout, 30-minute idle expiry, 8-hour absolute session expiry, and immediate local session revocation when access is deleted.
- Confirm Entra assignment removal/disabled accounts are blocked at the next Microsoft sign-in. Existing tracker sessions last until local revocation or expiry; for immediate removal, use **Delete access** in the tracker too.
- Exercise deleting/restoring a test cycle and check the underlying Drive file remains accessible to its existing authorized users.

Automated tests cover the local controls and mock the identity provider. They do **not** prove that a real university tenant, consent, credentials, or Conditional Access policy is correctly configured.

## Hosting

Run one instance on persistent local disk behind the university's HTTPS reverse proxy. Expose only HTTPS externally; bind the Python service to loopback (or an internal container network). The proxy should enforce the intended hostname, redirect HTTP to HTTPS, limit bodies to 5 MB, rate-limit sign-in requests, and set connection/request timeouts. Do not expose Python's port directly to the internet. The application ignores forwarded headers and uses `TRACKER_ORIGIN` for callbacks and same-origin mutation checks.

Docker example after the environment is configured:

```sh
docker build -t acbsp-tracker .
docker run -d --name acbsp-tracker --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e ENTRA_TENANT_ID -e ENTRA_CLIENT_ID -e ENTRA_CLIENT_SECRET \
  -e ENTRA_ADMIN_OBJECT_ID -e TRACKER_ORIGIN \
  --mount type=bind,source="$(pwd)/data",target=/app/data \
  acbsp-tracker
```

Give container UID 10001 access to the data directory on Linux. Store secrets using your host's secret injection mechanism rather than a committed env file. Keep dependencies and the base image patched. Configure encrypted disks, encrypted scheduled database backups, access-restricted backup retention, monitoring, and recovery drills before production. The SQLite file contains private records and pending sign-in flow state; the app does not encrypt that file itself.

Sessions use random opaque tokens (only SHA-256 digests are stored), HttpOnly/SameSite cookies, Secure cookies on HTTPS, idle/absolute expiry, and per-session CSRF tokens with exact Origin checks for writes. Server-side roles govern every mutation, including direct full-project API requests. A local audit table records sign-ins, project saves, archives/restores/purges, and user management. Admins can read the latest 200 events at `/api/audit`; it is not a tamper-proof external security log. Passwords and access tokens are not logged or retained.

## Archives and retention

Delete means archive. Cycles include their complete project; standards include criteria and semester tasks; criteria include their checklist references; review tasks and evidence links can also be restored. Restores preserve IDs and reject conflicting active records instead of overwriting them. Restore parent cycles/standards first. Older open browser tabs receive a revision conflict after restoration and must reload.

Permanent deletion removes only the selected archived tracker record. It cannot be restored through Archives afterward. Other archive entries and prior backups remain subject to your retention policy. A legacy migration snapshot in the `project` table and dated pre-change database backups are recovery copies, not active workspaces. No operation in this app deletes, moves, shares, or changes a linked cloud file. Cloud storage lifecycle and permissions remain with university IT/Drive owners.

**Evidence uploads are now supported.** The Evidence library stores file versions privately as SQLite BLOBs. Signed-in staff may upload files and updated versions; only admins may delete their tracker records. Uploaded bytes remain after archive purges. Copying a link never bypasses sign-in. See README for file types, limits, versioning, and retention.

## Recovery

Back up the entire SQLite database, not just per-cycle JSON exports: accounts, sessions, all cycles, archives, and audit records share the database. Stop the service before a filesystem copy, or use SQLite's backup API. Treat every backup as private. After restoring a database backup, clear `sessions` and `auth_flows` before reopening access so old sessions do not become valid again. Administrative recovery requires the server owner/IT and a backup; there is no publicly accessible reset endpoint.

References: [Microsoft MSAL authorization-code flow](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens#confidential-clients-interactive-token-acquisition), [Microsoft identity claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference), [Microsoft Graph signed-in user](https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0).

## Keep building locally while IT setup is pending

Run `.venv/bin/python -B run_local.py` from this project folder. It creates a random password in `.local-dev-password` (owner-only file permissions, excluded from Git and Docker). Open http://127.0.0.1:8000/login and paste that password into **Local development password**. You can edit the existing workspace as a clearly labeled local administrator; changes use the same saved database. Do not enter your university password.

This launcher forces binding to 127.0.0.1:8000. Login requires the exact local Host and Origin, a loopback connection, a correct password, and explicit development mode. Five attempts per minute are allowed. Normal server startup disables development login and rejects existing development sessions. Configuring Entra also disables it. The development launcher is not included in the Docker image. To switch back, stop the launcher and start `server.py` with the university configuration. Never deploy the development launcher or proxy its port.

## Evidence upload deployment

Upload requests use `application/octet-stream`, authenticated sessions, CSRF tokens, same-origin checks, a 10 MB per-file limit, generated storage IDs, extension/content checks, and a 1 GB cumulative storage cap. File bytes are outside the web root in SQLite. Downloads require authentication and are served as attachments with `nosniff` and a sandbox CSP, rather than rendering user documents in the portal’s origin. The upload endpoints are `/api/cycles/{cycle}/evidence` and `/api/evidence/{id}/versions`; configure the reverse proxy to allow 10 MB there (keep project JSON limits at 5 MB). Apply upload rate/concurrency limits at the proxy.

File signatures and Office package checks are **not malware scanning**. No antivirus/CDR service is configured. Before production use, IT should integrate its approved malware-scanning/quarantine process and validate upload controls against university policy. Keep ordinary document applications updated. File-replacement history is preserved, and concurrent replacement conflicts are rejected. Source: [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

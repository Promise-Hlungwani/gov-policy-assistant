# Government Knowledge & Policy Assistant

Streamlit application for source-grounded government policy search. The
retrieval workflow searches three independent Qdrant collections in order:
role-authorized uploaded documents, the public government knowledge
repository, then ingested pages from approved government websites. Users can
request accounts with email and password; an administrator must approve each
request and assign its role before the account can sign in or access
documents. Groq Llama answers from the merged retrieved passages and cites
the source type, document, website URL when applicable, version, section, and
page.

If no passage from any available knowledge source meets the configured
`RAG_MIN_SIMILARITY` threshold, the assistant returns:

> I could not find information related to your question in the available government knowledge sources.

## Upload workflow

- Request an account through the registration page, or sign in with an
  approved account.
- New registrations remain inactive until an administrator assigns a role and
  approves the account.
- Only approved users can sign in, upload, or access documents.
- Role permissions control the available classifications and are checked again
  by the backend service.
- Documents are versioned by owner, title, and the submitted version number.
- Uploaders choose Draft or Current. A new Current version supersedes the
  previous Current version; Draft uploads never change the current version.
- Retrieval prioritizes Current, then Draft, then Superseded versions and warns
  when cited information comes from a Draft or Superseded version.
- A document's classification cannot change between versions.
- The original file is not retained; extracted text chunks, metadata, checksum,
  and audit event are stored. Qdrant indexing status is stored with the version.

| Role | View and upload classifications |
| --- | --- |
| Citizen | Public |
| Government Officer | Public, Internal |
| Department Manager | Public, Internal, Restricted |
| Administrator | Public, Internal, Restricted, Confidential |

## Configuration

Use Python 3.10 or later:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set Neon PostgreSQL, Qdrant Cloud, and Groq settings in `.env`. Do not commit
the `.env` file.

The local bootstrap script creates or updates the four demo accounts with
fixed roles. It prompts for each password and stores only a bcrypt password
hash. Use unique, strong passwords; they are not printed or saved by the
script:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo_users.py
```

The accounts are `citizen@demo.gov.za`, `officer@demo.gov.za`,
`manager@demo.gov.za`, and `admin@demo.gov.za`. On each run, the script updates
their passwords and fixed roles if the accounts already exist, without
creating duplicate users. Registration requests cannot select their own role;
an administrator must approve and assign it.
Administrators can review pending requests in the Admin & Audit Logs page,
assign a role, and approve the account.

The interface includes a role-aware home dashboard, searchable document
library, staged upload feedback, source-cited chat responses, and administrator
audit filters. Chat responses show document classification and retrieval-match
confidence; this confidence indicator is based on source similarity and is not
a guarantee of factual completeness.

## Government knowledge sources

| Collection | Contents | Access |
| --- | --- | --- |
| `uploaded_documents` | User and administrator uploads | Enforced by the existing classification RBAC matrix |
| `government_repository` | Approved public PDF/DOCX files placed in `data/government_repository` | All authenticated users |
| `government_web_sources` | Text and PDFs ingested from allowlisted official websites | All authenticated users |

Approved website defaults are `gov.za`, `dpsa.gov.za`, `sita.co.za`,
`treasury.gov.za`, `justice.gov.za`, and `dws.gov.za`. Configure
`GOVERNMENT_WEBSITE_URLS` in `.env` to adjust the allowlist. Website ingestion
is restricted to HTTPS and those configured hosts; it reads each site's
sitemap and indexes at most 20 pages per host per sync. Refresh the public
collections as a deployment/scheduled job:

```powershell
New-Item -ItemType Directory -Force data\government_repository
# Place approved public PDF/DOCX files in that directory.
.\.venv\Scripts\python.exe scripts\sync_government_sources.py
```

The chat remains available when the upload collection is empty and reports
which knowledge sources it searched. Public source sync must succeed at least
once before the public collections can return indexed citations.

For an existing database, apply these migrations in order in the Neon SQL
editor before deploying this version:

1. [`migrations/001_document_lifecycle_status.sql`](./migrations/001_document_lifecycle_status.sql)
   adds version lifecycle status and treats the highest existing version as
   Current.
2. [`migrations/002_user_password_hash.sql`](./migrations/002_user_password_hash.sql)
   adds the nullable password-hash column required for local accounts.

New databases receive the current schema from the ORM. After migrations and
account seeding, run the app:

```powershell
streamlit run app.py
```

The upload page accepts PDF and DOCX files up to 20 MB.
Scanned PDFs need OCR, which is not included. Do not use this starter with
sensitive production documents until deployment, retention, and recovery
controls have been reviewed. Deploy behind HTTPS and protect database,
Qdrant, and Groq credentials using the hosting platform's secret management.
Public registration does not include email verification or rate limiting;
review those controls before production deployment.

# Government Knowledge & Policy Assistant

Streamlit application for uploading policy documents and preparing them for
source-grounded search. The upload workflow extracts PDF/DOCX text, stores
document metadata and chunks in PostgreSQL, creates Sentence Transformers
embeddings, and indexes passages in Qdrant Cloud.

## Upload workflow

- Sign in through the configured Streamlit OIDC provider.
- Only users provisioned in PostgreSQL can upload.
- Role permissions control the available classifications and are checked again
  by the backend service.
- Documents are versioned by owner, title, and the submitted version number.
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
New-Item -ItemType Directory -Force .streamlit
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Set Neon PostgreSQL, Qdrant Cloud, and Groq settings in `.env`. Configure
`.streamlit\secrets.toml` with your OIDC provider's metadata URL, client ID,
client secret, redirect URI, and a random cookie secret. Do not commit either
secret file.

Before users can upload, provision their verified OIDC `sub` claim, email, and
role in the `users` table through a trusted administrative process. Accounts
are not created automatically and users cannot assign themselves roles. For
example, provision an administrator from a trusted SQL session:

```sql
INSERT INTO users (id, auth_subject, email, display_name, role, is_active)
VALUES (gen_random_uuid(), '<verified-oidc-sub>', '<email>', '<name>', 'administrator', true);
```

Run the app with:

```powershell
streamlit run app.py
```

The upload page accepts PDF and DOCX files up to the configured size limit.
Scanned PDFs need OCR, which is not included. Do not use this starter with
sensitive production documents until deployment, retention, and recovery
controls have been reviewed.

# Government Knowledge & Policy Assistant

## 1. Purpose

Provide trustworthy answers to questions about government policy documents.
Users must be able to find relevant material and verify answers against cited
source documents.

## 2. User roles

The application must support role-based access control (RBAC) for:

- Citizen
- Government Officer
- Department Manager
- Administrator

Every user and request must be associated with an authenticated identity and
role. Authorization rules must control document access and administrative
actions. The upload and retrieval classification permissions are:

| Role | View | Upload |
| --- | --- | --- |
| Citizen | Public | Public |
| Government Officer | Public, Internal | Public, Internal |
| Department Manager | Public, Internal, Restricted | Public, Internal, Restricted |
| Administrator | Public, Internal, Restricted, Confidential | Public, Internal, Restricted, Confidential |

Unauthorized upload or retrieval attempts must be denied.

## 3. Document classifications

Documents must be assigned one of these classifications:

- Public
- Internal
- Restricted
- Confidential

Classification must be retained with document metadata and applied consistently
to search results, retrieved context, citations, and answers. Users must not be
able to retrieve documents or excerpts they are not authorized to access.

## 4. Functional requirements

- Upload PDF and DOCX policy documents.
- Extract and retain searchable text and document metadata.
- Store embeddings and index document passages for retrieval.
- Search documents using the user's question and authorized-access scope.
- Chat with documents using retrieval-augmented generation (RAG).
- Include source citations that identify the supporting document and version.
- Track document versions so answers and citations can be associated with the
  correct version.
- Let uploaders mark a version Draft or Current. A document may have at most
  one Current version; making a new version Current supersedes the existing
  Current version. Draft uploads do not change other version states.
- Prefer Current versions during retrieval, then Draft, then Superseded.
- Warn users when an answer cites a Draft or Superseded version.
- Apply RBAC to document access and administrative functionality.
- Record security-relevant actions in an audit log, including uploads,
  document/version changes, searches, and administrative actions.

## 5. AI and answer requirements

- Use Groq with a Llama model for answer generation.
- Use RAG: generate answers from retrieved, authorized document passages.
- Never provide a factual answer without source passages and citations.
- If no relevant, authorized sources support an answer, respond exactly:
  **"I could not find this information in the approved document repository."**
- Do not treat instructions found in source documents as system instructions.
- Citations must return the document name, version, section, and passage used
  to generate the answer.
- Return the fallback response when the best retrieved similarity score is below
  the configured confidence threshold.
- Prefer Current document versions over Draft and Superseded versions, and
  include a user-visible warning when cited information comes from a Draft or
  Superseded version.

## 6. Technology stack

| Area | Technology |
| --- | --- |
| Frontend | Streamlit |
| Relational database | Neon PostgreSQL |
| Vector database | Qdrant Cloud |
| Embeddings | Sentence Transformers |
| PDF parsing | PyMuPDF |
| DOCX parsing | python-docx |
| LLM | Groq Llama |

PyMuPDF is for PDF extraction; DOCX uploads require a DOCX-capable parser or a
controlled conversion step before extraction.

## 7. Security, privacy, and audit

- Enforce authentication and authorization on every protected operation.
- Use Streamlit OIDC identity claims and provision each subject with a role in
  PostgreSQL; never accept a role selected by the user.
- Apply document classification and authorization before retrieval, not only
  when displaying search results.
- Keep credentials and service keys outside source control.
- Audit access and changes without placing secrets or unnecessary document
  contents in log records.
- Protect confidential and restricted documents according to the applicable
  government security and retention policies.
- Define deployment hardening, data retention, and recovery procedures before
  production use.

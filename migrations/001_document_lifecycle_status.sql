BEGIN;

ALTER TABLE document_versions
    ADD COLUMN lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'current';

UPDATE document_versions AS version
SET lifecycle_status = 'superseded'
WHERE EXISTS (
    SELECT 1
    FROM document_versions AS newer
    WHERE newer.document_id = version.document_id
      AND newer.version_number > version.version_number
);

ALTER TABLE document_versions
    ADD CONSTRAINT ck_document_versions_lifecycle_status
    CHECK (lifecycle_status IN ('draft', 'current', 'superseded'));

CREATE UNIQUE INDEX uq_document_versions_one_current
    ON document_versions (document_id)
    WHERE lifecycle_status = 'current';

COMMIT;

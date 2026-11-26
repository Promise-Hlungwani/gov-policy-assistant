import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.government_source_ingestion_service import (
    GovernmentSourceIngestionService,
)
from utils.logging_config import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Index public government documents and approved government websites "
            "into their dedicated Qdrant collections."
        )
    )
    parser.add_argument(
        "--repository-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "government_repository",
        help="Directory containing approved public PDF and DOCX documents.",
    )
    parser.add_argument(
        "--skip-repository",
        action="store_true",
        help="Do not index local government repository documents.",
    )
    parser.add_argument(
        "--skip-websites",
        action="store_true",
        help="Do not fetch and index approved government websites.",
    )
    args = parser.parse_args()

    configure_logging()
    logger = logging.getLogger(__name__)
    indexer = GovernmentSourceIngestionService()
    try:
        repository_count = (
            0
            if args.skip_repository
            else indexer.ingest_repository_directory(args.repository_dir)
        )
        website_count = (
            0 if args.skip_websites else indexer.sync_approved_websites()
        )
    except (OSError, RuntimeError, ValueError):
        logger.exception("Government knowledge source synchronization failed.")
        return 1
    finally:
        indexer.close()

    logger.info(
        "Indexed %d repository documents and %d official website pages.",
        repository_count,
        website_count,
    )
    if repository_count + website_count == 0:
        logger.error(
            "No public sources were indexed. Check Qdrant configuration, source files, "
            "and approved website availability."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

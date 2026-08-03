"""Read precomputed whole-database counts for the front page.

The counts are written by the cobradb ETL (cobradb.summary_loading), which runs
as the final step of bin/load_db. This module only reads them, so the front page
costs one indexed query instead of a COUNT(*) per card on every request.
"""

import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from cobradb.models import DatabaseSummaryCount

# Must match cobradb.summary_loading.ENTITY_TYPES.
SUMMARY_ENTITY_TYPES = (
    "collections",
    "models",
    "metabolites",
    "reactions",
    "genomes",
    "compartments",
)


def get_summary_counts(session) -> Dict[str, int]:
    """Return {entity_type: count} for the front page cards.

    Never raises. If the summary table is missing (an ETL that predates this
    feature) or empty, an empty dict is returned and the front page simply
    omits the counts.
    """
    try:
        rows = session.execute(
            select(DatabaseSummaryCount.entity_type, DatabaseSummaryCount.count)
        ).all()
    except SQLAlchemyError as e:
        # do_safe_query only maps NotFoundError and ValueError, so an error here
        # would otherwise 500 the front page. Roll back so a poisoned connection
        # is not returned to the pool.
        session.rollback()
        logging.warning("Could not read database summary counts: %s", e)
        return {}

    return {entity_type: count for entity_type, count in rows}
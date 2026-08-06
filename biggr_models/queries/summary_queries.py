"""Read precomputed whole-database counts for the front page and statistics.

The counts are written by the cobradb ETL (cobradb.summary_loading), which runs
as the final step of bin/load_db. Every run appends a snapshot, so the table is
both the current totals and the history of how the database has grown. Reading
it costs one indexed query instead of a COUNT(*) per card on every request.
"""

import logging
from typing import Dict, List

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
            select(
                DatabaseSummaryCount.entity_type, DatabaseSummaryCount.count
            ).order_by(DatabaseSummaryCount.date_time)
        ).all()
    except SQLAlchemyError as e:
        # do_safe_query only maps NotFoundError and ValueError, so an error here
        # would otherwise 500 the front page. Roll back so a poisoned connection
        # is not returned to the pool.
        session.rollback()
        logging.warning("Could not read database summary counts: %s", e)
        return {}

    # The table holds one row per entity per ETL run. Ordering by date_time
    # means the newest row is assigned last, so the dict ends up holding the
    # current totals rather than an arbitrary older snapshot.
    return {entity_type: count for entity_type, count in rows}


def get_summary_history(session) -> Dict[str, List[Dict]]:
    """Return {entity_type: [{"date": ..., "count": ...}, ...]} oldest first.

    Never raises; an empty dict lets the statistics page explain that no
    history has been collected yet instead of returning a 500.
    """
    try:
        rows = session.execute(
            select(
                DatabaseSummaryCount.entity_type,
                DatabaseSummaryCount.date_time,
                DatabaseSummaryCount.count,
            ).order_by(DatabaseSummaryCount.date_time)
        ).all()
    except SQLAlchemyError as e:
        session.rollback()
        logging.warning("Could not read database summary history: %s", e)
        return {}

    history: Dict[str, List[Dict]] = {}
    for entity_type, date_time, count in rows:
        history.setdefault(entity_type, []).append(
            {"date": date_time, "count": count}
        )
    return history
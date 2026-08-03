"""Handler for the BiGGr front page."""

from biggr_models.handlers import utils
from biggr_models.queries.summary_queries import get_summary_counts


class HomeHandler(utils.BaseHandler):
    """Front page, with precomputed entity counts on the cards."""

    template = utils.env.get_template("index.html")

    def get(self):
        counts = utils.do_safe_query(get_summary_counts)
        # Wrap in a dict so the result stays truthy even when no counts are
        # available; return_result skips the context entirely on a falsy result.
        self.return_result({"counts": counts})
from biggr_models.queries import download_queries
from biggr_models.handlers import utils


class ReactionsDownloadHandler(utils.BaseHandler):
    def get(self):
        reactions = utils.do_safe_query(download_queries.get_reactions)

        self.set_header("Content-Type", "application/x-json")
        self.set_header(
            "Content-Disposition", 'attachment; filename="bigg_reactions.json"'
        )
        self.return_result(reactions)


class MetabolitesDownloadHandler(utils.BaseHandler):
    def get(self):
        metabolites = utils.do_safe_query(download_queries.get_metabolites)

        self.set_header("Content-Type", "application/x-json")
        self.set_header(
            "Content-Disposition", 'attachment; filename="bigg_metabolites.json"'
        )
        self.return_result(metabolites)

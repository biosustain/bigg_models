from cobradb.models import (
    Model,
    ModelReaction,
    Reaction,
    ReferenceReaction,
    UniversalReaction,
)
from biggr_models.handlers import utils
from biggr_models.queries import object_queries, reaction_queries, utils as query_utils
from functools import partial
import re
from cobradb.parse import hash_metabolite_dictionary


class UniversalReactionListViewHandler(utils.DataHandler):
    title = "Universal Reactions"
    column_specs = [
        utils.DataColumnSpec(
            UniversalReaction.bigg_id,
            "BiGG ID",
            hyperlink="/universal/reactions/${row['universalreaction__bigg_id']}",
        ),
        utils.DataColumnSpec(UniversalReaction.name, "Name"),
        # utils.DataColumnSpec(
        #     UniversalReaction.is_exchange, "Exchange", search_type="bool"
        # ),
        utils.DataColumnSpec(
            ReferenceReaction.bigg_id, "Reference", requires=UniversalReaction.reference
        ),
        utils.DataColumnSpec(
            UniversalReaction.is_transport, "Transport", search_type="bool"
        ),
        # utils.DataColumnSpec(UniversalReaction.is_pseudo, "Pseudo", search_type="bool"),
    ]
    page_data = {
        "row_icon": "reaction_S",
    }

    def pre_filter(self, query):
        return query.filter(UniversalReaction.collection_id == None)

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Universal", None),
            ("Reactions", "/universal/reactions/"),
        ]


class UniversalReactionHandler(utils.BaseHandler):
    template = utils.env.get_template("universal_reaction.html")

    def get(self, reaction_bigg_id):
        if self.is_api_request():
            return self.return_object(
                partial(object_queries.get_object, UniversalReaction), reaction_bigg_id
            )
        try:
            result = utils.do_safe_query(
                reaction_queries.get_universal_reaction_and_models, reaction_bigg_id
            )
        except query_utils.RedirectError as e:
            self.redirect(
                re.sub(self.request.path, "%s$" % reaction_bigg_id, e.args[0])
            )
        else:
            result["reaction_in_models_url"] = (
                f"/universal/reaction_in_models/{reaction_bigg_id}"
            )
            result["reaction_in_models_columns"] = (
                ReactionInModelsListViewHandler.column_specs
            )
            result["breadcrumbs"] = [
                ("Home", "/"),
                ("Universal", None),
                ("Reactions", f"/universal/reactions/"),
                (
                    utils.format_bigg_id(reaction_bigg_id, "reaction"),
                    f"/universal/reactions/{reaction_bigg_id}",
                ),
            ]

            self.return_result(result)


class ReactionInModelsListViewHandler(utils.DataHandler):
    title = "Reaction in Models"
    bigg_id = None
    page_data = {
        "row_icon": "model_S",
    }
    column_specs = [
        utils.DataColumnSpec(
            ModelReaction.bigg_id,
            "BiGG ID",
            hyperlink="/models/${row['model__bigg_id']}/reactions/${row['modelreaction__bigg_id']}",
            priority=1,
        ),
        utils.DataColumnSpec(
            Model.bigg_id,
            "Model",
            hyperlink="/models/${row['model__bigg_id']}",
            requires=[ModelReaction.model],
            priority=0,
        ),
        utils.DataColumnSpec(
            Model.organism,
            "Organism",
            requires=[ModelReaction.model],
            priority=2,
        ),
    ]

    def pre_filter(self, query):
        return (
            query.join(ModelReaction.reaction)
            .join(Reaction.universal_reaction)
            .filter(UniversalReaction.bigg_id == self.bigg_id)
        )


class ReactionListViewHandler(utils.DataHandler):
    title = "Reactions"
    model_bigg_id = None

    column_specs = [
        utils.DataColumnSpec(
            ModelReaction.bigg_id,
            "BiGG ID",
            hyperlink="/models/${row['model__bigg_id']}/reactions/${row['modelreaction__bigg_id']}",
        ),
        utils.DataColumnSpec(
            UniversalReaction.name,
            "Name",
            requires=[
                ModelReaction.reaction,
                Reaction.universal_reaction,
            ],
        ),
        utils.DataColumnSpec(
            ReferenceReaction.bigg_id,
            "Reference",
            requires=[
                ModelReaction.reaction,
                Reaction.universal_reaction,
                UniversalReaction.reference,
            ],
        ),
        utils.DataColumnSpec(Model.bigg_id, "Model", requires=ModelReaction.model),
        utils.DataColumnSpec(
            UniversalReaction.is_transport,
            "Transport",
            requires=[
                ModelReaction.reaction,
                Reaction.universal_reaction,
            ],
            search_type="bool",
        ),
    ]

    def pre_filter(self, query):
        return query.filter(Model.bigg_id == self.model_bigg_id)

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Models", "/models/"),
            (self.model_bigg_id, f"/models/{self.model_bigg_id}"),
            ("Reactions", f"/models/{self.model_bigg_id}/reactions/"),
        ]


class ReactionHandler(utils.BaseHandler):
    template = utils.env.get_template("reaction.html")

    def get(self, model_bigg_id, reaction_bigg_id):
        if self.is_api_request():
            return self.return_object(
                object_queries.get_model_reaction_object,
                reaction_bigg_id,
                model_bigg_id,
            )
        results = utils.safe_query(
            reaction_queries.get_model_reaction, model_bigg_id, reaction_bigg_id
        )

        results["breadcrumbs"] = [
            ("Home", "/"),
            ("Models", "/models/"),
            (model_bigg_id, f"/models/{model_bigg_id}/"),
            ("Reactions", f"/models/{model_bigg_id}/reactions/"),
            (
                utils.format_bigg_id(reaction_bigg_id, "reaction"),
                f"/models/{model_bigg_id}/reactions/{reaction_bigg_id}",
            ),
        ]

        self.return_result(results)


class ReactionWithStoichHandler(utils.BaseHandler):
    def get(self):
        metabolite_dict = {
            k: float(v[0]) for k, v in self.request.query_arguments.items()
        }
        hash = hash_metabolite_dictionary(metabolite_dict)
        session = utils.Session()
        try:
            results = {
                "results": [reaction_queries.reaction_with_hash(hash, session)],
                "results_count": 1,
            }
        except query_utils.NotFoundError:
            results = {"results": [], "results_count": 0}
        session.close()
        self.write(results)
        self.finish()

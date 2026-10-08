from typing import Optional
from cobradb.models import (
    Compartment,
    CompartmentalizedComponent,
    Component,
    Model,
    ModelCompartmentalizedComponent,
    ModelReaction,
    Reaction,
    ReactionMatrix,
    ReferenceCompound,
    ReferenceReaction,
    UniversalComponent,
    UniversalReaction,
)
from sqlalchemy import func, select
from biggr_models.handlers import utils
from biggr_models.queries import metabolite_queries, object_queries, utils as query_utils
from functools import partial

import re


class UniversalMetaboliteListViewHandler(utils.DataHandler):
    title = "Universal Metabolites"
    column_specs = [
        utils.DataColumnSpec(
            UniversalComponent.bigg_id,
            "BiGG ID",
            hyperlink="/universal/metabolites/${row['universalcomponent__bigg_id']}",
        ),
        utils.DataColumnSpec(UniversalComponent.name, "Name"),
    ]
    page_data = {
        "card_lead": "List of universal metabolites in the database. Each univeral metabolite can have multiple metabolite instances that represent different protonation states. Click a row in the table below to display these different metabolite instances.",
        "row_icon": "molecule_S",
    }

    def pre_filter(self, query):
        return query.filter(UniversalComponent.collection_id == None)

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Universal", None),
            ("Metabolites", "/universal/metabolites/"),
        ]


class UniversalMetaboliteHandler(utils.BaseHandler):
    template = utils.env.get_template("universal_metabolite.html")

    def get(self, met_bigg_id):
        if self.is_api_request():
            return self.return_object(
                partial(object_queries.get_object, UniversalComponent), met_bigg_id
            )
        try:
            result = utils.safe_query(metabolite_queries.get_metabolite, met_bigg_id)
        except query_utils.RedirectError as e:
            self.redirect(re.sub(self.request.path, "%s$" % met_bigg_id, e.args[0]))
        else:
            result["breadcrumbs"] = [
                ("Home", "/"),
                ("Universal", None),
                ("Metabolites", f"/universal/metabolites/"),
                (met_bigg_id, f"/universal/metabolites/{met_bigg_id}"),
            ]
            self.return_result(result)


class MetaboliteListViewHandler(utils.DataHandler):
    title = "Metabolites"
    model_bigg_id: Optional[str] = None
    column_specs = [
        utils.DataColumnSpec(
            ModelCompartmentalizedComponent.bigg_id,
            "BiGG ID",
            hyperlink="/models/${row['model__bigg_id']}/metabolites/${row['modelcompartmentalizedcomponent__bigg_id']}",
        ),
        utils.DataColumnSpec(
            Component.name,
            "Name",
            requires=[
                ModelCompartmentalizedComponent.compartmentalized_component,
                CompartmentalizedComponent.component,
            ],
        ),
        utils.DataColumnSpec(
            Compartment.bigg_id,
            "Compartment",
            requires=[
                ModelCompartmentalizedComponent.compartmentalized_component,
                CompartmentalizedComponent.compartment,
            ],
        ),
        utils.DataColumnSpec(
            Model.bigg_id, "Model", requires=ModelCompartmentalizedComponent.model
        ),
        utils.DataColumnSpec(
            (Component.collection_id != None),
            "Collection-specific",
            requires=[
                ModelCompartmentalizedComponent.compartmentalized_component,
                CompartmentalizedComponent.component,
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
            ("Metabolites", f"/models/{self.model_bigg_id}/metabolites/"),
        ]


class MetaboliteHandler(utils.BaseHandler):
    template = utils.env.get_template("metabolite.html")

    def get(self, model_bigg_id, comp_met_id):
        if self.is_api_request():
            return self.return_object(
                metabolite_queries.get_model_compartmentalized_component_object,
                comp_met_id,
                model_bigg_id,
            )
        results = utils.safe_query(
            metabolite_queries.get_model_comp_metabolite,
            comp_met_id,
            model_bigg_id,
        )
        results["breadcrumbs"] = [
            ("Home", "/"),
            ("Models", "/models/"),
            (model_bigg_id, f"/models/{model_bigg_id}/"),
            ("Metabolites", f"/models/{model_bigg_id}/metabolites/"),
            (
                utils.format_bigg_id(comp_met_id, "comp_comp"),
                f"/models/{model_bigg_id}/metabolites/{comp_met_id}",
            ),
        ]
        self.return_result(results)


class MetaboliteInModelsListViewHandler(utils.DataHandler):
    title = "Metabolite in Models"
    bigg_id: Optional[str] = None
    page_data = {
        "row_icon": "model_S",
    }
    column_specs = [
        # utils.DataColumnSpec(
        #     ModelCompartmentalizedComponent.bigg_id,
        #     "BiGG ID",
        #     hyperlink="/models/${row['model__bigg_id']}/metabolites/${row['modelcompartmentalizedcomponent__bigg_id']}",
        #     priority=1,
        # ),
        utils.DataColumnSpec(
            CompartmentalizedComponent.bigg_id,
            "BiGG ID",
            requires=[
                ModelCompartmentalizedComponent.compartmentalized_component,
            ],
            hyperlink="/models/${row['model__bigg_id']}/metabolites/${row['compartmentalizedcomponent__bigg_id']}",
            priority=1,
        ),
        utils.DataColumnSpec(
            Compartment.bigg_id,
            "Compartment",
            requires=[
                ModelCompartmentalizedComponent.compartmentalized_component,
                CompartmentalizedComponent.compartment,
            ],
            priority=2,
        ),
        utils.DataColumnSpec(
            Component.charge,
            "Charge",
            search_type="number",
            priority=3,
        ),
        utils.DataColumnSpec(
            Model.bigg_id,
            "Model",
            hyperlink="/models/${row['model__bigg_id']}",
            requires=[ModelCompartmentalizedComponent.model],
            priority=0,
        ),
        utils.DataColumnSpec(
            Model.organism,
            "Organism",
            requires=[ModelCompartmentalizedComponent.model],
            priority=4,
        ),
    ]

    def pre_filter(self, query):
        return (
            query.join(ModelCompartmentalizedComponent.compartmentalized_component)
            .join(CompartmentalizedComponent.component)
            .join(Component.universal_component)
            .filter(UniversalComponent.bigg_id == self.bigg_id)
        )


class MetaboliteInReactionsListViewHandler(utils.DataHandler):
    title = "Metabolite in Reactions"
    bigg_id: Optional[str] = None
    model_bigg_id: Optional[str] = None
    page_data = {
        "row_icon": "reaction_S",
    }
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
        utils.DataColumnSpec(
            UniversalReaction.is_transport,
            "Transport",
            requires=[
                ModelReaction.reaction,
                Reaction.universal_reaction,
            ],
            search_type="bool",
        ),
        utils.DataColumnSpec(
            (Reaction.collection_id != None),
            "Collection-specific",
            requires=[
                ModelReaction.reaction,
            ],
            search_type="bool",
        ),
        utils.DataColumnSpec(
            Model.bigg_id,
            "Model",
            requires=[
                ModelReaction.model,
            ],
            visible=False,
        ),
    ]

    def pre_filter(self, query):
        selection_subq = (
            select(ModelReaction.id.label("mr_id"))
            .join(ModelReaction.model)
            .filter(Model.bigg_id == self.model_bigg_id)
            .join(ModelReaction.reaction)
            .join(Reaction.matrix)
            .join(ReactionMatrix.compartmentalized_component)
            .join(
                CompartmentalizedComponent.model_compartmentalized_components.and_(
                    ModelCompartmentalizedComponent.model_id == Model.id,
                    ModelCompartmentalizedComponent.bigg_id == self.bigg_id,
                )
            )
            .group_by(ModelReaction.id)
            .having(func.count(ModelCompartmentalizedComponent.id) > 0)
            .subquery()
        )
        return query.join(selection_subq, selection_subq.c.mr_id == ModelReaction.id)

from biggr_models.handlers import utils
from typing import Optional
from biggr_models.queries import object_queries
from biggr_models.queries.compartment_queries import get_compartment
from functools import partial
from sqlalchemy import select, func
from cobradb.models import (
    Compartment,
    CompartmentalizedComponent,
    Model,
    ModelCollection,
    ModelCompartmentalizedComponent,
    ModelCount,
)


class CompartmentListViewHandler(utils.DataHandler):
    title = "Compartments"
    column_specs = [
        utils.DataColumnSpec(
            Compartment.bigg_id,
            "BiGG ID",
            hyperlink="/compartments/${row['compartment__bigg_id']}",
        ),
        utils.DataColumnSpec(
            Compartment.name,
            "Name",
            hyperlink="/compartments/${row['compartment__bigg_id']}",
        ),
    ]

    def breadcrumbs(self):
        return [("Home", "/"), ("Compartments", "/compartments/")]


class ModelsWithCompartmentListViewHandler(utils.DataHandler):
    title = "Models with Compartment"
    bigg_id: Optional[str] = None
    column_specs = [
        utils.DataColumnSpec(
            Model.bigg_id, "BiGG ID", hyperlink="/models/${row['model__bigg_id']}"
        ),
        utils.DataColumnSpec(Model.organism, "Organism"),
        utils.DataColumnSpec(
            ModelCollection.bigg_id,
            "Collection",
            requires=[Model.collection],
            hyperlink="/collections/${row['modelcollection__bigg_id']}/",
        ),
        utils.DataColumnSpec(
            ModelCount.metabolite_count,
            "Metabolites",
            requires=Model.model_count,
            global_search=False,
            hyperlink="/models/${row['model__bigg_id']}/metabolites",
            search_type="number",
        ),
        utils.DataColumnSpec(
            ModelCount.reaction_count,
            "Reactions",
            requires=Model.model_count,
            global_search=False,
            hyperlink="/models/${row['model__bigg_id']}/reactions",
            search_type="number",
        ),
        utils.DataColumnSpec(
            ModelCount.gene_count,
            "Genes",
            requires=Model.model_count,
            global_search=False,
            hyperlink="/models/${row['model__bigg_id']}/genes",
            search_type="number",
        ),
    ]
    page_data = {
        "row_icon": "model_S",
    }

    def pre_filter(self, query):
        subq = (
            select(Model.id)
            .join(Model.model_compartmentalized_components)
            .join(ModelCompartmentalizedComponent.compartmentalized_component)
            .join(CompartmentalizedComponent.compartment)
            .filter(Compartment.bigg_id == self.bigg_id)
            .group_by(Model.id)
            .having(func.count(Compartment.id) > 0)
            .subquery()
        )
        query = query.join(subq, subq.c.id == Model.id)
        return query

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Compartments", "/compartments/"),
            (self.bigg_id, f"/compartments/{self.bigg_id}"),
            ("Models", f"/compartments/{self.bigg_id}/models"),
        ]


class CompartmentHandler(utils.BaseHandler):
    template = utils.env.get_template("compartment.html")

    def get(self, compartment_bigg_id):
        if self.is_api_request():
            return self.return_object(
                partial(object_queries.get_object, Compartment), compartment_bigg_id
            )
        result = utils.do_safe_query(get_compartment, compartment_bigg_id)
        result["breadcrumbs"] = [
            ("Home", "/"),
            ("Compartments", "/compartments/"),
            (compartment_bigg_id, f"/compartments/{compartment_bigg_id}"),
        ]
        self.return_result(result)

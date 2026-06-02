from cobradb.models import Model, ModelCount, ModelCollection
from biggr_models.handlers import utils
from biggr_models.queries import model_queries
from os import path


class ModelsListViewHandler(utils.DataHandler):
    title = "Models"
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
        "disable_default_order": True,
    }

    def breadcrumbs(self):
        return [("Home", "/"), ("Models", "/models/")]

    def post_filter(self, query):
        # Default order: oldest loaded first
        return query.order_by(Model.date_modified.asc(), Model.id.asc())


class ModelCollectionHandler(utils.DataHandler):
    title = "Models in Collection"
    collection_bigg_id = None
    page_data = {"row_icon": "model_S"}

    column_specs = [
        utils.DataColumnSpec(
            Model.bigg_id, "BiGG ID", hyperlink="/models/${row['model__bigg_id']}"
        ),
        utils.DataColumnSpec(Model.organism, "Organism"),
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

    def pre_filter(self, query):
        return query.join(Model.collection).filter(
            ModelCollection.bigg_id == self.collection_bigg_id
        )

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Collections", "/collections/"),
            (self.collection_bigg_id, f"/collections/{self.collection_bigg_id}/"),
        ]


class ModelDownloadHandler(utils.BaseHandler):
    def get(self, model_bigg_id):
        with open(
            path.join(utils.directory, "static", "models", "%s.json" % model_bigg_id)
        ) as f:
            json_str = f.read()
        self.write(json_str)
        self.set_header("Content-type", "application/json; charset=utf-8")
        self.finish()


class ModelHandler(utils.BaseHandler):
    template = utils.env.get_template("model.html")

    def get(self, model_bigg_id):
        result = utils.safe_query(
            model_queries.get_model_and_counts,
            model_bigg_id,
            static_model_dir=utils.static_model_dir,
        )
        result["breadcrumbs"] = [
            ("Home", "/"),
            ("Models", "/models/"),
            (model_bigg_id, f"/models/{model_bigg_id}"),
        ]

        result["model_metrics"] = [
            {
                "label": "Metabolites",
                "link": f"/models/{model_bigg_id}/metabolites",
                "value": result["metabolite_count"],
            },
            {
                "label": "Reactions",
                "link": f"/models/{model_bigg_id}/reactions",
                "value": result["reaction_count"],
            },
            {
                "label": "Genes",
                "link": f"/models/{model_bigg_id}/genes",
                "value": result["gene_count"],
            },
        ]

        result["model_properties"] = []
        if result["genome_name"] is not None:
            result["model_properties"].append(
                {
                    "label": "Genome",
                    "link": f"/genomes/{result['genome_ref_string']}",
                    "value": result["genome_name"],
                }
            )
        if result["reference_type"] == "pmid":
            result["model_properties"].append(
                {
                    "label": "Publication PMID",
                    "link": f"https://www.ncbi.nlm.nih.gov/pubmed/{result['reference_id']}",
                    "value": result["reference_id"],
                }
            )
        elif result["reference_type"] == "doi":
            result["model_properties"].append(
                {
                    "label": "Publication DOI",
                    "link": f"https://dx.doi.org/{result['reference_id']}",
                    "value": result["reference_id"],
                }
            )

        self.return_result(result)


class ModelCollectionsTreeViewHandler(utils.BaseHandler):
    template = utils.env.get_template("modelcollections_treeview.html")

    def get(self):
        result = utils.do_safe_query(
            model_queries.get_model_collections_and_taxons,
        )
        result["breadcrumbs"] = [
            ("Home", "/"),
            ("Collections", "/collections/"),
        ]

        self.return_result(result)

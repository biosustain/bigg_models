from biggr_models import __api_version__ as api_v
from typing import Any, Dict, Optional, Type
from tornado.routing import URLSpec
from tornado.web import RequestHandler
from biggr_models.handlers import (
    advanced_search_handlers,
    data_access_handlers,
    identifiers_handlers,
    download_handlers,
    escher_handlers,
    home_handlers,
    utils,
    object_handlers,
    reaction_handlers,
    compartment_handlers,
    gene_handlers,
    genome_handlers,
    metabolite_handlers,
    model_handlers,
    db_interop_handlers,
)
from os import path
from tornado.web import RedirectHandler


def url(
    pattern: str,
    handler: Type[RequestHandler],
    kwargs: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
) -> URLSpec:
    """Helper function to create a tornado.routing.URLSpec.

    Using this function will cause the name argument to also be inserted
    as a URLSpec keyword argument. Usefull if the handler is (derived from)
    the DataHandler class."""
    if name is None:
        return URLSpec(pattern, handler, kwargs)
    if kwargs is None:
        opts = {"name": name}
    else:
        opts = kwargs
        opts["name"] = name
    return URLSpec(pattern, handler, opts, name=name)


def get_routes():
    api_regex = r"(?P<api>/api/%s)?" % api_v
    routes = [
        (r"/", home_handlers.HomeHandler),
        (r"/about/?", utils.TemplateHandler, {"template_name": "about.html"}),
        (
            r"/api/%s/objects/?$" % api_v,
            object_handlers.ObjectHandler,
        ),
        (
            r"/api/%s/identifiers/?$" % api_v,
            identifiers_handlers.IdentifiersHandler,
        ),
        url(
            api_regex + r"/universal/reactions/?$",
            reaction_handlers.UniversalReactionListViewHandler,
            name="reactions",
        ),
        #
        (
            r"/(?:api/%s/)?(?:models/)?universal/reactions/([^/]+)/?$" % api_v,
            reaction_handlers.UniversalReactionHandler,
        ),
        url(
            api_regex + r"/universal/metabolites/?$",
            metabolite_handlers.UniversalMetaboliteListViewHandler,
            name="metabolites",
        ),
        url(
            api_regex + r"/universal/metabolite_in_models/(?P<bigg_id>[^/]+)/?$",
            metabolite_handlers.MetaboliteInModelsListViewHandler,
            name="metabolites_for_model",
        ),
        #
        (
            r"/(?:api/%s/)?(?:models/)?universal/metabolites/([^/]+)/?$" % api_v,
            metabolite_handlers.UniversalMetaboliteHandler,
        ),
        #
        url(
            api_regex + r"/compartments/?$",
            compartment_handlers.CompartmentListViewHandler,
            name="compartments",
        ),
        #
        (
            r"/(?:api/%s/)?compartments/([^/]+)/?$" % api_v,
            compartment_handlers.CompartmentHandler,
        ),
        url(
            api_regex + r"/compartments/(?P<bigg_id>[^/]+)/models/?$",
            compartment_handlers.ModelsWithCompartmentListViewHandler,
            name="models_with_compartment",
        ),
        #
        url(
            api_regex + r"/genomes/?$",
            genome_handlers.GenomeListViewHandler,
            name="genomes",
        ),
        url(
            api_regex
            + r"/genomes/(?P<accession_type>[^/:]+):(?P<accession_value>[^/]+)/genes/?$",
            gene_handlers.GenesInGenomeListViewHandler,
            name="genes_in_genomes",
        ),
        (
            r"/genomes/(?P<accession_type>[^/:]+):(?P<accession_value>[^/]+)/genes/(?P<gene_bigg_id>[^/]+)/?$",
            gene_handlers.GenomeGeneHandler,
        ),
        #
        (
            r"/(?:api/%s/)?genomes/([^/]+)/?$" % api_v,
            genome_handlers.GenomeHandler,
        ),
        url(
            r"/collections/?$",
            model_handlers.ModelCollectionsTreeViewHandler,
        ),
        url(
            api_regex + r"/collections/(?P<collection_bigg_id>[^/]+)/?$",
            model_handlers.ModelCollectionHandler,
            name="model_collection",
        ),
        #
        # By model
        #
        url(
            api_regex + r"/models/?$",
            model_handlers.ModelsListViewHandler,
            name="models",
        ),
        #
        (r"/(?:api/%s/)?models/([^/]+)/?$" % api_v, model_handlers.ModelHandler),
        #
        (
            r"/(?:api/%s/)?models/([^/]+)/download/?$" % api_v,
            model_handlers.ModelDownloadHandler,
        ),
        #
        (
            r"/(?:api/%s/)?models/([^/]+)/reactions/([^/]+)/?$" % api_v,
            reaction_handlers.ReactionHandler,
        ),
        url(
            api_regex + r"/models/(?P<model_bigg_id>[^/]+)/reactions/?$",
            reaction_handlers.ReactionListViewHandler,
            name="model_reactions",
        ),
        url(
            api_regex + r"/models/(?P<model_bigg_id>[^/]+)/metabolites/?$",
            metabolite_handlers.MetaboliteListViewHandler,
            name="model_metabolites",
        ),
        url(
            api_regex
            + r"/models/(?P<model_bigg_id>[^/]+)/metabolite_in_reactions/(?P<bigg_id>[^/]+)/?$",
            metabolite_handlers.MetaboliteInReactionsListViewHandler,
            name="model_reactions_for_model_metabolite",
        ),
        url(
            api_regex + r"/models/(?P<model_bigg_id>[^/]+)/genes/?$",
            gene_handlers.GeneListViewHandler,
            name="model_genes",
        ),
        url(
            api_regex
            + r"/models/(?P<model_bigg_id>[^/]+)/escher/(?P<map_bigg_id>[^/]+)/?$",
            escher_handlers.EscherHandler,
            name="escher_maps",
        ),
        #
        (
            r"/(?:api/%s/)?models/([^/]+)/metabolites/([^/]+)/?$" % api_v,
            metabolite_handlers.MetaboliteHandler,
        ),
        #
        (
            r"/(?:api/%s/)?models/([^/]+)/genes/([^/]+)/?$" % api_v,
            gene_handlers.GeneHandler,
        ),
        #
        # Download
        (r"/api/v3/download/reactions/?$", download_handlers.ReactionsDownloadHandler),
        (
            r"/api/v3/download/metabolites/?$",
            download_handlers.MetabolitesDownloadHandler,
        ),
        #
        # Search
        (
            r"/search/(?P<search_query>.*)$",
            advanced_search_handlers.SearchResultsHandler,
        ),
        url(
            api_regex + r"/search/genomes/(?P<search_query>.*)$",
            advanced_search_handlers.GenomeSearchHandler,
            name="search_genomes",
        ),
        url(
            api_regex + r"/search/genes/(?P<search_query>.*)$",
            advanced_search_handlers.GeneSearchHandler,
            name="search_genes",
        ),
        url(
            api_regex + r"/search/metabolites/(?P<search_query>.*)$",
            advanced_search_handlers.UniversalMetaboliteSearchHandler,
            name="search_metabolites",
        ),
        url(
            api_regex + r"/search/metabolites_ref/(?P<search_query>.*)$",
            advanced_search_handlers.MetaboliteReferenceSearchHandler,
            name="search_metabolites_via_reference",
        ),
        url(
            api_regex
            + r"/search/metabolites_ann/(?P<data_source>.*)/(?P<search_query>.*)$",
            advanced_search_handlers.MetaboliteAnnotationSearchHandler,
            name="search_metabolites_via_annotation",
        ),
        url(
            api_regex + r"/search/metabolites_inchikey/(?P<search_query>.*)$",
            advanced_search_handlers.MetaboliteInChIKeySearchHandler,
            name="search_metabolites_via_inchikey",
        ),
        url(
            api_regex + r"/search/reactions/(?P<search_query>.*)$",
            advanced_search_handlers.UniversalReactionSearchHandler,
            name="search_reactions",
        ),
        url(
            api_regex + r"/search/reactions_ref/(?P<search_query>.*)$",
            advanced_search_handlers.UniversalReactionReferenceSearchHandler,
            name="search_reactions_via_reference",
        ),
        url(
            api_regex
            + r"/search/reactions_ann/(?P<data_source>.*)/(?P<search_query>.*)$",
            advanced_search_handlers.UniversalReactionAnnotationSearchHandler,
            name="search_reactions_via_annotation",
        ),
        url(
            api_regex + r"/search/reactions_ec/(?P<search_query>.*)$",
            advanced_search_handlers.UniversalReactionECSearchHandler,
            name="search_reactions_via_ec",
        ),
        url(
            api_regex + r"/search/models/(?P<search_query>.*)$",
            advanced_search_handlers.ModelSearchHandler,
            name="search_models",
        ),
        #
        # Pages
        (r"/web_api$", RedirectHandler, {"url": "/data_access"}),
        (r"/api$", RedirectHandler, {"url": "/data_access"}),
        (
            r"/data_access/?",
            data_access_handlers.DataAccessPageHandler,
        ),
        # (
        #     r"/license$",
        #     utils.TemplateHandler,
        #     {"template_name": "about_license_page.html"},
        # ),
        # (
        #     r"/about$",
        #     utils.TemplateHandler,
        #     {"template_name": "about_license_page.html"},
        # ),
        # (r"/updates$", utils.TemplateHandler, {"template_name": "updates.html"}),
        #
        # Version
        (r"/api/%s/database_version$" % api_v, utils.APIVersionHandler),
        #
        # Static/Download
        (
            r"/(favicon.ico)$",
            utils.StaticFileHandlerWithEncoding,
            {"path": path.join(utils.directory, "static", "assets", "favicon")},
        ),
        (
            r"/static/models/(.*)$",
            utils.StaticFileDownloadHandler,
            {"path": path.join(utils.directory, "static", "models")},
        ),
        (
            r"/static/(.*)$",
            utils.StaticFileHandlerWithEncoding,
            {"path": path.join(utils.directory, "static")},
        ),
        (r"/interop-query/query-by-gene/?$", db_interop_handlers.QueryByGeneHandler),
        (
            r"/interop-query/query-by-strain/?$",
            db_interop_handlers.QueryByStrainHandler,
        ),
        (r"/interop-query/query-by-pair/?$", db_interop_handlers.QueryByPairHandler),
        (r"/interop-query/strains/?$", db_interop_handlers.StrainListHandler),
        (r"/interop-query/genes/?$", db_interop_handlers.GeneListHandler),
        (r"/interop-query/gene-strain-pairs/?$", db_interop_handlers.GeneStrainPairListHandler),
    ]
    return routes

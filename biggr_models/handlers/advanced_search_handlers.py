from cobradb.models import (
    Annotation,
    AnnotationLink,
    AnnotationProperty,
    Chromosome,
    Component,
    ComponentIDMapping,
    ComponentReferenceMapping,
    DataSource,
    Gene,
    Genome,
    InChI,
    Model,
    ModelCollection,
    Reaction,
    ReferenceCompound,
    ReferenceReaction,
    ReferenceReactionAnnotationMapping,
    UniversalComponent,
    UniversalReaction,
)
from sqlalchemy import distinct, and_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import aggregate_strings
from biggr_models.handlers import utils
from biggr_models.queries import utils as query_utils

ALLOWED_SEARCH_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "_+-()[]/:.,' &;{}=?`|#*^"
)


# agg_strings = lambda x: aggregate_strings(x, ", ")
# agg_strings = lambda x: array_agg(distinct(x))
def agg_strings(x):
    return aggregate_strings(distinct(x), ", ")


def process_string_array(x):
    return ", ".join(x)


def get_data_source_id(session: Session, bigg_id: str):
    return session.scalars(
        select(DataSource.id).filter(DataSource.bigg_id == bigg_id).limit(1)
    ).first()


DATA_SOURCE_IDS = {
    "RHEA": utils.do_safe_query(get_data_source_id, "rhea"),
    "seed.compound": utils.do_safe_query(get_data_source_id, "seed.compound"),
    "seed.reaction": utils.do_safe_query(get_data_source_id, "seed.reaction"),
    "kegg.compound": utils.do_safe_query(get_data_source_id, "kegg.compound"),
    "kegg.reaction": utils.do_safe_query(get_data_source_id, "kegg.reaction"),
    "metacyc.compound": utils.do_safe_query(get_data_source_id, "metacyc.compound"),
    "metacyc.reaction": utils.do_safe_query(get_data_source_id, "metacyc.reaction"),
    "metanetx.chemical": utils.do_safe_query(get_data_source_id, "metanetx.chemical"),
    "metanetx.reaction": utils.do_safe_query(get_data_source_id, "metanetx.reaction"),
    "ec-code": utils.do_safe_query(get_data_source_id, "ec-code"),
}


class GenomeSearchHandler(utils.DataHandler):
    title = "Genomes"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            Genome.accession_value,
            "Accession",
            hyperlink=(
                "/genomes/"
                "${row['genome__accession_type']}:"
                "${row['genome__accession_value']}"
            ),
        ),
        utils.DataColumnSpec(
            Genome.accession_type,
            "Type",
        ),
        utils.DataColumnSpec(
            Genome.organism,
            "Organism",
            agg_func=agg_strings,
        ),
        utils.DataColumnSpec(
            Chromosome.ncbi_accession,
            "Chromosomes",
            agg_func=agg_strings,
            requires=[Genome.chromosomes],
        ),
    ]

    def post_filter(self, query):
        return query.group_by(Genome.accession_value, Genome.accession_type)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class GeneSearchHandler(utils.DataHandler):
    title = "Genes"
    search_query: str = ""
    column_specs = [
        # utils.DataColumnSpec(
        #     Gene.id,
        #     "ID",
        #     apply_search_query=False,
        # ),
        utils.DataColumnSpec(
            Gene.bigg_id,
            "BiGG ID",
            agg_func=agg_strings,
            hyperlink=(
                "/genomes/${row['genome__accession_type']}:"
                "${row['genome__accession_value']}/genes/${row['gene__bigg_id']}"
            ),
        ),
        utils.DataColumnSpec(
            Gene.name,
            "Name",
            agg_func=agg_strings,
        ),
        utils.DataColumnSpec(
            Gene.locus_tag,
            "Locus Tag",
            agg_func=agg_strings,
        ),
        utils.DataColumnSpec(
            Genome.accession_type,
            "Genome Type",
            agg_func=agg_strings,
            requires=[Gene.chromosome, Chromosome.genome],
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            Genome.accession_value,
            "Genome Accession",
            agg_func=agg_strings,
            requires=[Gene.chromosome, Chromosome.genome],
            apply_search_query=False,
        ),
    ]

    def post_filter(self, query):
        return query.group_by(Gene.id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class UniversalMetaboliteSearchHandler(utils.DataHandler):
    title = "Universal Metabolites"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            UniversalComponent.bigg_id,
            "BiGG ID",
            hyperlink="/universal/metabolites/${row['universalcomponent__bigg_id']}",
        ),
        utils.DataColumnSpec(
            Component.name,
            "Names",
            agg_func=agg_strings,
            # process=process_string_array,
            requires=[UniversalComponent.components],
        ),
        utils.DataColumnSpec(
            ComponentIDMapping.old_bigg_id,
            "Old BiGG IDs",
            agg_func=agg_strings,
            requires=[UniversalComponent.old_bigg_ids],
        ),
        utils.DataColumnSpec(
            AnnotationProperty.value_str,
            "Synonyms",
            agg_func=agg_strings,
            # process=process_string_array,
            requires=[
                UniversalComponent.components,
                Component.all_annotations,
                Annotation.properties.and_(AnnotationProperty.key == "name"),
            ],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(UniversalComponent.collection_id == None)

    def post_filter(self, query):
        return query.group_by(UniversalComponent.bigg_id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class MetaboliteReferenceSearchHandler(utils.DataHandler):
    title = "Metabolites via Reference"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            Component.bigg_id,
            "BiGG ID",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            Component.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            UniversalComponent.bigg_id,
            "Universal BiGG ID",
            agg_func=agg_strings,
            requires=[Component.universal_component],
            hyperlink="/universal/metabolites/${row['universalcomponent__bigg_id']}",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            ReferenceCompound.bigg_id,
            "Reference Compound",
            agg_func=agg_strings,
            requires=[
                Component.reference_mappings,
                ComponentReferenceMapping.reference_compound,
            ],
            score_modes=["exact"],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(Component.collection_id == None)

    def post_filter(self, query):
        return query.group_by(Component.bigg_id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class MetaboliteAnnotationSearchHandler(utils.DataHandler):
    title = "Metabolites via Annotation"
    search_query: str = ""
    data_source: str = ""
    column_specs = [
        utils.DataColumnSpec(
            Component.bigg_id,
            "BiGG ID",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            Component.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            UniversalComponent.bigg_id,
            "Universal BiGG ID",
            agg_func=agg_strings,
            requires=[Component.universal_component],
            hyperlink="/universal/metabolites/${row['universalcomponent__bigg_id']}",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            AnnotationLink.identifier,
            "Annotation",
            agg_func=agg_strings,
            requires=[
                Component.all_annotations,
                Annotation.links,
            ],
            score_modes=["exact"],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(Component.collection_id == None).filter(
            AnnotationLink.data_source_id == DATA_SOURCE_IDS[self.data_source]
        )

    def post_filter(self, query):
        return query.group_by(Component.bigg_id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class MetaboliteInChIKeySearchHandler(utils.DataHandler):
    title = "Metabolites by InChIKey"
    search_query: str = ""
    data_source: str = ""
    column_specs = [
        utils.DataColumnSpec(
            Component.bigg_id,
            "BiGG ID",
            apply_search_query=False,
            priority=0,
        ),
        utils.DataColumnSpec(
            Component.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
            priority=4,
        ),
        utils.DataColumnSpec(
            UniversalComponent.bigg_id,
            "Universal BiGG ID",
            agg_func=agg_strings,
            requires=[Component.universal_component],
            hyperlink="/universal/metabolites/${row['universalcomponent__bigg_id']}",
            apply_search_query=False,
            priority=1,
        ),
        utils.DataColumnSpec(
            InChI.key_major,
            "InChIKey [major-*-*]",
            agg_func=agg_strings,
            requires=[
                Component.reference_mappings,
                ComponentReferenceMapping.reference_compound,
                ReferenceCompound.inchi,
            ],
            score_modes=["exact"],
            priority=5,
        ),
        utils.DataColumnSpec(
            InChI.key_minor,
            "InChIKey [*-minor-*]",
            agg_func=agg_strings,
            requires=[
                Component.reference_mappings,
                ComponentReferenceMapping.reference_compound,
                ReferenceCompound.inchi,
            ],
            apply_search_query=False,
            priority=3,
        ),
        utils.DataColumnSpec(
            InChI.key_proton,
            "InChIKey [*-*-proton]",
            agg_func=agg_strings,
            requires=[
                Component.reference_mappings,
                ComponentReferenceMapping.reference_compound,
                ReferenceCompound.inchi,
            ],
            apply_search_query=False,
            priority=2,
        ),
    ]

    def pre_filter(self, query):
        inchi_query = self.parse_inchi_key(self.search_query)
        if inchi_query is None:
            return query.filter(False)
        query = (
            query.join(Component.reference_mappings)
            .join(ComponentReferenceMapping.reference_compound)
            .join(ReferenceCompound.inchi)
        )
        filters = [InChI.key_major == inchi_query["inchi__key_major"]]
        if (key_minor := inchi_query["inchi__key_minor"]) is not None:
            filters.append(InChI.key_minor == key_minor)
        if (key_proton := inchi_query["inchi__key_proton"]) is not None:
            filters.append(InChI.key_proton == key_proton)
        return query.filter(and_(*filters))

    def post_filter(self, query):
        return query.group_by(Component.bigg_id)

    def parse_inchi_key(self, search_query):
        inchikey = search_query.strip().rstrip("-")
        if ":" in search_query:
            namespace, inchikey = search_query.split(":", maxsplit=1)
            if namespace.upper() != "INCHIKEY":
                return None
        parts = [x.strip().upper() for x in inchikey.split("-")]
        if len(parts) > 3:
            return None
        if len(parts) == 3:
            major_part, minor_part, proton_part = parts
        elif len(parts) == 2:
            major_part, minor_part = parts
            proton_part = None
        else:
            major_part = parts[0]
            minor_part, proton_part = None, None
        if len(major_part) != 14:
            return None
        if minor_part is not None and len(minor_part) != 10:
            return None
        if proton_part is not None and len(proton_part) != 1:
            return None
        return {
            "inchi__key_major": major_part,
            "inchi__key_minor": minor_part,
            "inchi__key_proton": proton_part,
        }

    def return_data(self, search_query, *args, **kwargs):
        inchi_query = self.parse_inchi_key(search_query)
        if inchi_query is None:
            self.write_data([], 0, 0)
            return
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=inchi_query
        )
        self.write_data(data, total, filtered)


class UniversalReactionSearchHandler(utils.DataHandler):
    title = "Universal Reactions"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            UniversalReaction.bigg_id,
            "BiGG ID",
            hyperlink="/universal/reactions/${row['universalreaction__bigg_id']}",
        ),
        utils.DataColumnSpec(
            UniversalReaction.name,
            "Name",
        ),
        utils.DataColumnSpec(
            AnnotationProperty.value_str,
            "Synonyms",
            agg_func=agg_strings,
            # process=process_string_array,
            requires=[
                UniversalReaction.reactions,
                Reaction.all_annotations,
                Annotation.properties.and_(AnnotationProperty.key == "name"),
            ],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(UniversalReaction.collection_id == None)

    def post_filter(self, query):
        return query.group_by(UniversalReaction.bigg_id, UniversalReaction.name)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class UniversalReactionReferenceSearchHandler(utils.DataHandler):
    title = "Reactions via Reference"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            UniversalReaction.bigg_id,
            "BiGG ID",
            hyperlink="/universal/reactions/${row['universalreaction__bigg_id']}",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            UniversalReaction.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            ReferenceReaction.bigg_id,
            "Reference",
            agg_func=agg_strings,
            requires=[UniversalReaction.reference],
            score_modes=["exact"],
        ),
        utils.DataColumnSpec(
            ("RHEA:" + AnnotationLink.identifier),
            "Alternative Reference IDs",
            agg_func=agg_strings,
            requires=[
                UniversalReaction.reference,
                ReferenceReaction.annotation_mappings,
                ReferenceReactionAnnotationMapping.annotation,
                Annotation.links,
            ],
            score_modes=["exact"],
            search_query_remove_namespace=True,
        ),
    ]

    def pre_filter(self, query):
        return query.filter(UniversalReaction.collection_id == None)

    def post_filter(self, query):
        return query.group_by(UniversalReaction.bigg_id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class UniversalReactionAnnotationSearchHandler(utils.DataHandler):
    title = "Reactions via Annotation"
    search_query: str = ""
    data_source: str = ""
    column_specs = [
        utils.DataColumnSpec(
            UniversalReaction.bigg_id,
            "BiGG ID",
            hyperlink="/universal/reactions/${row['universalreaction__bigg_id']}",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            UniversalReaction.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            AnnotationLink.identifier,
            "Annotation",
            agg_func=agg_strings,
            requires=[
                UniversalReaction.reactions,
                Reaction.all_annotations,
                Annotation.links,
            ],
            score_modes=["exact"],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(UniversalReaction.collection_id == None).filter(
            AnnotationLink.data_source_id == DATA_SOURCE_IDS[self.data_source]
        )

    def post_filter(self, query):
        return query.group_by(UniversalReaction.bigg_id)

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class UniversalReactionECSearchHandler(utils.DataHandler):
    title = "Reactions via EC"
    search_query: str = ""
    data_source: str = ""
    column_specs = [
        utils.DataColumnSpec(
            UniversalReaction.bigg_id,
            "BiGG ID",
            hyperlink="/universal/reactions/${row['universalreaction__bigg_id']}",
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            UniversalReaction.name,
            "Name",
            agg_func=agg_strings,
            apply_search_query=False,
        ),
        utils.DataColumnSpec(
            AnnotationLink.identifier,
            "EC-code",
            agg_func=agg_strings,
            requires=[
                UniversalReaction.reactions,
                Reaction.all_annotations,
                Annotation.links,
            ],
            score_modes=["exact", "startswith"],
        ),
    ]

    def pre_filter(self, query):
        return query.filter(UniversalReaction.collection_id == None).filter(
            AnnotationLink.data_source_id == DATA_SOURCE_IDS["ec-code"]
        )

    def post_filter(self, query):
        query = query.group_by(UniversalReaction.bigg_id)
        return query

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


class ModelSearchHandler(utils.DataHandler):
    title = "Models"
    search_query: str = ""
    column_specs = [
        utils.DataColumnSpec(
            Model.bigg_id,
            "BiGG ID",
            hyperlink="/models/${row['model__bigg_id']}",
        ),
        utils.DataColumnSpec(
            Model.organism,
            "Organism",
        ),
        utils.DataColumnSpec(
            ModelCollection.bigg_id,
            "Collection",
            requires=[Model.collection],
        ),
        utils.DataColumnSpec(
            ModelCollection.description,
            "Collection Description",
            requires=[Model.collection],
        ),
    ]

    def post_filter(self, query):
        query = query.group_by(
            Model.bigg_id,
            Model.organism,
            ModelCollection.bigg_id,
            ModelCollection.description,
        )
        return query

    def return_data(self, search_query, *args, **kwargs):
        data, total, filtered = self.data_query(
            query_utils.get_search_list, search_query=search_query
        )
        self.write_data(data, total, filtered)


S_API = "/api/v3/search"


class SearchResultsHandler(utils.BaseHandler):
    template = utils.env.get_template("search_results.html")

    def clean_search_query(self, search_query):
        return "".join(x for x in search_query.strip() if x in ALLOWED_SEARCH_ALPHABET)

    def build_special_tab_page(self, search_query):
        if ":" in search_query:
            namespace, identifier = search_query.split(":", maxsplit=1)
        else:
            if search_query.startswith("cpd"):
                namespace = "seed.compound"
                identifier = search_query
            elif search_query.startswith("rxn"):
                namespace = "seed.reaction"
                identifier = search_query

            elif search_query.startswith("MNX"):
                namespace = "metanetx"
                identifier = search_query
            else:
                namespace = "BIGG"
                identifier = search_query
        namespace = namespace.upper()
        identifier = identifier.strip()

        if namespace == "SEED":
            if identifier.startswith("cpd"):
                namespace = "SEED.COMPOUND"
            else:
                namespace = "SEED.REACTION"

        if namespace == "KEGG":
            if identifier.startswith("C"):
                namespace = "KEGG.COMPOUND"
            else:
                namespace = "KEGG.REACTION"

        if namespace == "METANETX":
            if identifier.startswith("MNXM"):
                namespace = "METANETX.CHEMICAL"
            else:
                namespace = "METANETX.REACTION"

        if namespace == "METACYC":
            if identifier.startswith("RXN-") or identifier.endswith("-RXN"):
                namespace = "METACYC.REACTION"
            else:
                namespace = "METACYC.COMPOUND"

        if namespace == "EC":
            namespace = "EC-CODE"

        if namespace == "EC-CODE":
            identifier = identifier.rstrip("*")

        if namespace == "CHEBI":
            return {
                "id": "special_page",
                "title": "Reference",
                "data_url": f"{S_API}/metabolites_ref/{namespace}:{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteReferenceSearchHandler.column_specs,
                "message": "Interpreted search query as a reference metabolite entry.",
            }
        elif namespace == "RHEA":
            return {
                "id": "special_page",
                "title": "Reference",
                "data_url": f"{S_API}/reactions_ref/{namespace}:{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionReferenceSearchHandler.column_specs,
                "message": "Interpreted search query as a reference reaction entry.",
            }
        elif namespace == "SEED.COMPOUND":
            return {
                "id": "special_page",
                "title": "SEED",
                "data_url": f"{S_API}/metabolites_ann/seed.compound/{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a ModelSEED metabolite entry.",
            }
        elif namespace == "SEED.REACTION":
            return {
                "id": "special_page",
                "title": "SEED",
                "data_url": f"{S_API}/reactions_ann/seed.reaction/{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a ModelSEED reaction entry.",
            }

        elif namespace == "KEGG.COMPOUND":
            return {
                "id": "special_page",
                "title": "KEGG",
                "data_url": f"{S_API}/metabolites_ann/kegg.compound/{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a KEGG metabolite entry.",
            }
        elif namespace == "KEGG.REACTION":
            return {
                "id": "special_page",
                "title": "KEGG",
                "data_url": f"{S_API}/reactions_ann/kegg.reaction/{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a KEGG reaction entry.",
            }

        elif namespace == "METANETX.CHEMICAL":
            return {
                "id": "special_page",
                "title": "MetaNetX",
                "data_url": f"{S_API}/metabolites_ann/metanetx.chemical/{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a MetaNetX metabolite entry.",
            }
        elif namespace == "METANETX.REACTION":
            return {
                "id": "special_page",
                "title": "MetaNetX",
                "data_url": f"{S_API}/reactions_ann/metanetx.reaction/{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a MetaNetX reaction entry.",
            }

        elif namespace == "METACYC.COMPOUND":
            return {
                "id": "special_page",
                "title": "MetaCyc",
                "data_url": f"{S_API}/metabolites_ann/metacyc.compound/{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a MetaCyc metabolite entry.",
            }
        elif namespace == "METACYC.REACTION":
            return {
                "id": "special_page",
                "title": "MetaCyc",
                "data_url": f"{S_API}/reactions_ann/metacyc.reaction/{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionAnnotationSearchHandler.column_specs,
                "message": "Interpreted search query as a MetaCyc reaction entry.",
            }
        elif namespace == "INCHIKEY":
            return {
                "id": "special_page",
                "title": "InChIKey",
                "data_url": f"{S_API}/metabolites_inchikey/{identifier}",
                "row_icon": "molecule_S",
                "columns": MetaboliteInChIKeySearchHandler.column_specs,
                "message": "Interpreted search query as an InChIKey.",
            }
        elif namespace == "EC-CODE":
            return {
                "id": "special_page",
                "title": "EC-code",
                "data_url": f"{S_API}/reactions_ec/{identifier}",
                "row_icon": "reaction_S",
                "columns": UniversalReactionECSearchHandler.column_specs,
                "message": "Interpreted search query as an EC-code.",
            }

        return None

    def get(self, search_query):
        if not search_query.strip():
            search_query = self.get_argument("search_query", "")
        search_query = self.clean_search_query(search_query)

        special_page = self.build_special_tab_page(search_query)
        special_page = [special_page] if special_page is not None else []
        data = {
            "search_query": search_query,
            "result_types": special_page
            + [
                {
                    "id": "model",
                    "title": "Models",
                    "data_url": utils.get_reverse_url(
                        self,
                        "search_models",
                        {"api": "/api/v3", "search_query": search_query},
                    ),
                    "columns": ModelSearchHandler.column_specs,
                    "row_icon": "model_S",
                },
                {
                    "id": "universal_component",
                    "title": "Metabolites",
                    "data_url": utils.get_reverse_url(
                        self,
                        "search_metabolites",
                        {"api": "/api/v3", "search_query": search_query},
                    ),
                    "columns": UniversalMetaboliteSearchHandler.column_specs,
                    "row_icon": "molecule_S",
                },
                {
                    "id": "universal_reaction",
                    "title": "Reactions",
                    "data_url": utils.get_reverse_url(
                        self,
                        "search_reactions",
                        {"api": "/api/v3", "search_query": search_query},
                    ),
                    "columns": UniversalReactionSearchHandler.column_specs,
                    "row_icon": "reaction_S",
                },
                {
                    "id": "genomes",
                    "title": "Genomes",
                    "data_url": utils.get_reverse_url(
                        self,
                        "search_genomes",
                        {"api": "/api/v3", "search_query": search_query},
                    ),
                    "columns": GenomeSearchHandler.column_specs,
                    "row_icon": "genome_S",
                },
                {
                    "id": "genes",
                    "title": "Genes",
                    "data_url": utils.get_reverse_url(
                        self,
                        "search_genes",
                        {"api": "/api/v3", "search_query": search_query},
                    ),
                    "columns": GeneSearchHandler.column_specs,
                    "row_icon": "gene_S",
                },
            ],
            "breadcrumbs": [("Home", "/"), ("Search", None), (search_query, None)],
        }
        self.return_result(data)

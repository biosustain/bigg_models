from typing import Iterable, List, Optional, Tuple, Union
from sqlalchemy.orm import Session, joinedload, subqueryload
from biggr_models.queries import utils
from dataclasses import dataclass

from cobradb.util import ref_tuple_to_str
from cobradb import settings
from cobradb.models import (
    EscherModule,
    Model,
    ModelCount,
    ModelCollection,
    ModelReaction,
    ModelReactionEscherMapping,
    PublicationModel,
    Taxon,
    TaxonomicRank,
)

from sqlalchemy import func, select
from os import path

from biggr_models.queries.memote_queries import get_general_results_for_model


def get_models_count(session, **kwargs):
    """Return the number of models in the database."""
    query = session.scalars(select(func.count(Model.id))).first()
    return query


def get_models(
    session,
    page=None,
    size=None,
    sort_column=None,
    sort_direction="ascending",
):
    """Get models and number of components.

    Arguments
    ---------

    session: An ome session object.

    page: The page, or None for all pages.

    size: The page length, or None for all pages.

    sort_column: The name of the column to sort. Must be one of 'bigg_id',
    'organism', 'metabolite_count', 'reaction_count', and 'gene_count'.

    sort_direction: Either 'ascending' or 'descending'.

    Returns
    -------

    A list of objects with keys 'bigg_id', 'organism', 'metabolite_count',
    'reaction_count', and 'gene_count'.

    """
    # get the sort column
    columns = {
        "bigg_id": func.lower(Model.bigg_id),
        "organism": func.lower(Model.organism),
        "metabolite_count": ModelCount.metabolite_count,
        "reaction_count": ModelCount.reaction_count,
        "gene_count": ModelCount.gene_count,
    }

    if sort_column is None:
        sort_column_object = None
    else:
        try:
            sort_column_object = columns[sort_column]
        except KeyError:
            print("Bad sort_column name: %s" % sort_column)
            sort_column_object = next(iter(columns.values()))

    # set up the query
    query = select(
        Model.bigg_id,
        Model.organism,
        ModelCount.metabolite_count,
        ModelCount.reaction_count,
        ModelCount.gene_count,
    ).join(Model.model_count)
    # order and limit
    query = utils._apply_order_limit_offset(
        query, sort_column_object, sort_direction, page, size
    )
    query = session.execute(query).all()

    return [
        {
            "bigg_id": x[0],
            "organism": x[1],
            "metabolite_count": x[2],
            "reaction_count": x[3],
            "gene_count": x[4],
        }
        for x in query
    ]


def get_model_and_counts(
    model_bigg_id,
    session,
    static_model_dir=None,
):
    model_db = session.scalars(
        select(
            Model,
        )
        .options(
            joinedload(Model.collection),
            joinedload(Model.model_count),
            joinedload(Model.genome),
            subqueryload(Model.publication_models).joinedload(
                PublicationModel.publication
            ),
        )
        .filter(Model.bigg_id == model_bigg_id)
        .limit(1)
    ).first()
    if model_db is None:
        raise utils.NotFoundError("No Model found with BiGG ID " + model_bigg_id)

    escher_modules = list(
        session.scalars(
            select(EscherModule)
            .join(EscherModule.model_reaction_mappings)
            .join(ModelReactionEscherMapping.model_reaction)
            .filter(ModelReaction.model_id == model_db.id)
            .group_by(EscherModule.id)
            .having(func.count(ModelReactionEscherMapping.id) > 1)
        ).all()
    )
    # genome ref
    genome_strain = None
    organism = getattr(model_db, "organism", None)
    if model_db.genome is None:
        genome_ref_string = genome_name = None
    else:
        genome_name = model_db.genome.accession_value
        genome_ref_string = ref_tuple_to_str(
            model_db.genome.accession_type, genome_name
        )
        genome_strain = model_db.genome.strain
        if organism is None:
            organism = model_db.genome.organism
        if (
            organism is not None
            and genome_strain is not None
            and genome_strain in organism
        ):
            genome_strain = None

    publication = next((x.publication for x in model_db.publication_models), None)
    result = {
        "model_bigg_id": model_db.bigg_id,
        "collection_bigg_id": model_db.collection.bigg_id,
        "published_filename": model_db.published_filename,
        "method": model_db.method,
        "organism": organism,
        "strain": genome_strain,
        "genome_name": genome_name,
        "genome_ref_string": genome_ref_string,
        "metabolite_count": model_db.model_count.metabolite_count,
        "reaction_count": model_db.model_count.reaction_count,
        "gene_count": model_db.model_count.gene_count,
        "reference_type": None if publication is None else publication.reference_type,
        "reference_id": None if publication is None else publication.reference_id,
        "escher_modules": escher_modules,
        "model_modified_date": model_db.date_modified.strftime("%b %d, %Y"),
        # "last_updated": session.query(DatabaseVersion)
        # .first()
        # .date_time.strftime("%b %d, %Y"),
    }

    memote_result_db = get_general_results_for_model(session, model_db.id)
    result["memote_result"] = memote_result_db

    if static_model_dir:
        # get filesizes
        for ext in ("xml", "xml_gz", "mat", "mat_gz", "json", "json_gz"):
            fpath = path.join(
                static_model_dir, model_bigg_id + "." + ext.replace("_", ".")
            )
            byte_size = path.getsize(fpath) if path.isfile(fpath) else 0
            if byte_size > 1048576:
                result[ext + "_size"] = "%.1f MB" % (byte_size / 1048576.0)
            elif byte_size > 1024:
                result[ext + "_size"] = "%.1f kB" % (byte_size / 1024.0)
            elif byte_size > 0:
                result[ext + "_size"] = "%d B" % (byte_size)
    return result


def get_model_list(session):
    """Return a list of all models, for advanced search."""
    model_list = session.scalars(Model.bigg_id)
    l = [x[0] for x in model_list]
    l.sort()
    return l


def get_model_json_string(model_bigg_id):
    """Get the model JSON for download."""
    fpath = path.join(settings.model_dump_directory, model_bigg_id + ".json")
    try:
        with open(fpath, "r") as f:
            data = f.read()
    except IOError as e:
        raise utils.NotFoundError(e.message)
    return data


def get_model_object(
    session: Session,
    id: utils.IDType,
):
    id_sel = utils.convert_id_to_query_filter(id, Model)
    model_db = session.scalars(
        select(Model)
        .options(
            joinedload(Model.genome),
            joinedload(Model.model_count),
            subqueryload(Model.publication_models),
        )
        .filter(id_sel)
        .limit(1)
    ).first()

    if model_db is None:
        raise utils.NotFoundError(f"No Model found with BiGG ID {id}")

    return {"id": id, "object": model_db}


def get_taxons_recursively(session: Session, starting_id: Union[int, Iterable[int]]):
    # WITH RECURSIVE cte AS (SELECT id, name, parent_id FROM taxonomy t WHERE t.id = 668369 UNION SELECT t2.id, t2.name, t2.parent_id FROM taxonomy t2 JOIN cte ON cte.parent_id = t2.id) SELECT * FROM cte;
    topq = select(Taxon.id, Taxon.parent_id, Taxon.name, Taxon.rank_id)
    if isinstance(starting_id, Iterable):
        topq = topq.filter(Taxon.id.in_(starting_id))
    else:
        topq = topq.filter(Taxon.id == starting_id)
    topq = topq.cte("cte", recursive=True)

    bottomq = select(Taxon.id, Taxon.parent_id, Taxon.name, Taxon.rank_id)
    bottomq = bottomq.join(topq, Taxon.id == topq.c.parent_id)

    recursive_q = topq.union(bottomq)
    q = select(recursive_q)
    return session.execute(q).all()


@dataclass
class TreeNode:
    name: str
    children: List["TreeNode"]

    def recursive_collapse(self, parent=None, stops=None):
        children = self.children[:]
        for child in children:
            child.recursive_collapse(self, stops=stops)

    @property
    def node_type(self):
        return self.__class__.__name__.lower().replace("treenode", "")

    def __repr__(self):
        return self._indented_repr()

    def __str__(self):
        return self._indented_repr()

    def _indented_repr(self, depth: int = 0):
        s = [f"{'  ' * depth}<{self.__class__.__name__} name='{self.name}'>"]
        for child in self.children:
            s.append(child._indented_repr(depth + 1))
        return "\n".join(s)


@dataclass
class TaxonTreeNode(TreeNode):
    tax_id: int
    rank_id: int
    hidden_taxons: Optional[List[Tuple[int, str, int]]] = None

    def recursive_collapse(self, parent=None, stops=None):
        keep_going = True
        while keep_going:
            keep_going = False
            if stops is not None and self.rank_id in stops:
                break
            if len(self.children) == 1 and isinstance(
                single_child := self.children[0], TaxonTreeNode
            ):
                if self.name != "cellular organisms":
                    # Remove 'cellular organisms' from the tree
                    if self.hidden_taxons is None:
                        self.hidden_taxons = []
                    self.hidden_taxons.append((self.tax_id, self.name, self.rank_id))
                self.tax_id = single_child.tax_id
                self.rank_id = single_child.rank_id
                self.name = single_child.name
                self.children = single_child.children
                keep_going = True

        super().recursive_collapse(parent=parent, stops=stops)


@dataclass
class CollectionTreeNode(TreeNode):
    collection: ModelCollection

    def recursive_collapse(self, parent=None, stops=None):
        if parent is None:
            return
        # Collapse single-model collections in the tree
        if len(self.children) == 1:
            parent.children.remove(self)
            single_child = self.children[0]
            parent.children.append(single_child)
            single_child.recursive_collapse(parent, stops=stops)


@dataclass
class ModelTreeNode(TreeNode):
    model: Model


def get_model_collections_and_taxons(session: Session):
    collections_db = session.scalars(
        select(ModelCollection).options(
            subqueryload(ModelCollection.models).joinedload(Model.genome)
        )
    ).all()

    tax_ids = set()
    for collection in collections_db:
        tax_ids.add(collection.taxon_id)
        # for model in collection.models:
        #     tax_ids.add(model.taxon_id)
    try:
        tax_ids.remove(None)
    except KeyError:
        pass

    stop_rank_ids = list(
        session.scalars(
            select(TaxonomicRank.id).filter(
                TaxonomicRank.name.in_(["domain", "family", "class", "species"])
            )
        ).all()
    )

    taxons = get_taxons_recursively(session, starting_id=tax_ids)

    tree = next(
        TaxonTreeNode(name=name, tax_id=tax_id, rank_id=rank_id, children=[])
        for tax_id, _, name, rank_id in taxons
        if name == "root"
    )

    front: List[TaxonTreeNode] = [tree]
    while front:
        old_front = front
        front = []
        for node in old_front:
            new_nodes_gen = (
                TaxonTreeNode(name=name, tax_id=tax_id, rank_id=rank_id, children=[])
                for tax_id, parent_id, name, rank_id in taxons
                if parent_id == node.tax_id and tax_id != node.tax_id
            )
            for new_node in new_nodes_gen:
                node.children.append(new_node)
                front.append(new_node)
            collection_node_gen = [
                CollectionTreeNode(
                    name=collection.bigg_id,
                    collection=collection,
                    children=[
                        ModelTreeNode(name=model.bigg_id, model=model, children=[])
                        for model in collection.models
                    ],
                )
                for collection in collections_db
                if collection.taxon_id == node.tax_id
            ]
            node.children.extend(collection_node_gen)

    # Join taxon nodes with only one (taxon) child.
    for child in tree.children:
        if isinstance(child, TaxonTreeNode):
            child.recursive_collapse(parent=tree, stops=stop_rank_ids)

    return {"tree": tree}

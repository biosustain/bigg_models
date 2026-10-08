from collections.abc import Iterable
from typing import Any, Type
from cobradb.models import (
    Annotation,
    AnnotationLink,
    Base,
    Chromosome,
    Compartment,
    CompartmentalizedComponent,
    Component,
    Genome,
    InChI,
    MemoteResult,
    MemoteTest,
    Model,
    ModelCollection,
    ModelReaction,
    Publication,
    Reaction,
    ReactionMatrix,
    ReferenceCompound,
    ReferenceReaction,
    ReferenceReactionParticipant,
    ReferenceReactivePart,
    ReferenceReactivePartMatrix,
    Taxon,
    TaxonomicRank,
    UniversalComponent,
    UniversalReaction,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload, subqueryload

from cobradb.parse import split_id_and_copy_tag
from cobradb.util import ref_str_to_tuple

from biggr_models.queries import utils

OBJECT_DEFAULT_LOAD = {
    Model: (
        joinedload(Model.genome),
        joinedload(Model.model_count),
        joinedload(Model.collection),
        subqueryload(Model.publication_models),
    ),
    ModelCollection: (),
    Reaction: (
        joinedload(Reaction.collection),
        subqueryload(Reaction.matrix).joinedload(
            ReactionMatrix.compartmentalized_component
        ),
    ),
    UniversalReaction: (joinedload(UniversalReaction.reference),),
    ReferenceReaction: (
        subqueryload(ReferenceReaction.reaction_participants).joinedload(
            ReferenceReactionParticipant.compound
        )
    ),
    Component: (),
    UniversalComponent: (
        joinedload(UniversalComponent.reference_mapping),
        joinedload(UniversalComponent.collection),
        subqueryload(UniversalComponent.components),
    ),
    CompartmentalizedComponent: (joinedload(CompartmentalizedComponent.compartment),),
    ReferenceCompound: (
        joinedload(ReferenceCompound.inchi),
        subqueryload(ReferenceCompound.reactive_part_matrix).joinedload(
            ReferenceReactivePartMatrix.reactive_part
        ),
    ),
    ReferenceReactivePart: (
        joinedload(ReferenceReactivePart.inchi),
        subqueryload(ReferenceReactivePart.matrix).joinedload(
            ReferenceReactivePartMatrix.compound
        ),
    ),
    Genome: (subqueryload(Genome.chromosomes),),
    Chromosome: (joinedload(Chromosome.genome)),
    Compartment: (),
    Publication: (subqueryload(Publication.publication_models),),
    InChI: (),
    MemoteTest: (),
    MemoteResult: (
        joinedload(MemoteResult.test),
        joinedload(MemoteResult.model),
        joinedload(MemoteResult.model_reaction),
        joinedload(MemoteResult.model_compartmentalized_component),
        joinedload(MemoteResult.model_gene),
    ),
    Annotation: (
        subqueryload(Annotation.links).joinedload(AnnotationLink.data_source),
    ),
    Taxon: (joinedload(Taxon.rank),),
    TaxonomicRank: (),
}


def get_object(
    obj_type: Type[Base],
    session: Session,
    id: utils.IDType,
):
    id_sel = utils.convert_id_to_query_filter(id, obj_type)
    obj_db = session.scalars(
        select(obj_type).options(*OBJECT_DEFAULT_LOAD[obj_type]).filter(id_sel).limit(1)
    ).first()

    if obj_db is None:
        raise utils.NotFoundError(f"No Object found with BiGG ID {id}")

    return {"id": id, "object": obj_db}


def get_object_property(
    parent_obj_type: Type[Base],
    obj_type: Type[Base],
    property: Any,
    session: Session,
    id: int,
):
    id_sel = utils.convert_id_to_query_filter(id, parent_obj_type)
    obj_db = session.scalars(
        select(parent_obj_type)
        .options(subqueryload(property).options(*OBJECT_DEFAULT_LOAD.get(obj_type, ())))
        .filter(id_sel)
        .limit(1)
    ).first()

    if obj_db is None:
        raise utils.NotFoundError(f"No Object found with BiGG ID {id}")

    results = getattr(obj_db, property.key)

    if isinstance(results, Iterable):
        results = list(results)

    return {"id": id, "objects": results}


def get_model_reaction_object(
    session: Session,
    id: utils.IDType,
    model_id: utils.IDType,
):
    """Get a reaction as it appears in a model, by its BiGG ID in that model
    (e.g. ACODA, or ACODA:2 for a second copy)."""
    query = (
        select(ModelReaction)
        .join(ModelReaction.reaction)
        .join(Reaction.universal_reaction)
        .join(ModelReaction.model)
        .options(
            contains_eager(ModelReaction.reaction).contains_eager(
                Reaction.universal_reaction
            ),
            contains_eager(ModelReaction.model),
        )
        .filter(utils.convert_id_to_query_filter(model_id, Model))
    )
    if isinstance(id, int):
        query = query.filter(ModelReaction.id == id)
    else:
        reaction_bigg_id, copy_number = split_id_and_copy_tag(id)
        query = query.filter(UniversalReaction.bigg_id == reaction_bigg_id).filter(
            ModelReaction.copy_number == copy_number
        )
    model_reaction_db = session.scalars(query.limit(1)).first()

    if model_reaction_db is None:
        raise utils.NotFoundError(f"No Reaction {id} found in model {model_id}")

    return {"id": id, "model_id": model_id, "object": model_reaction_db}


def get_genome_object_by_accession(session: Session, id: str):
    """Get a genome by its accession reference (e.g. ncbi_assembly:GCF_000005845.2)."""
    try:
        accession_type, accession_value = ref_str_to_tuple(id)
    except Exception:
        raise utils.NotFoundError(f"No Genome found with ID {id}")
    genome_id = session.scalars(
        select(Genome.id)
        .filter(Genome.accession_type == accession_type)
        .filter(Genome.accession_value == accession_value)
        .limit(1)
    ).first()
    if genome_id is None:
        raise utils.NotFoundError(f"No Genome found with ID {id}")
    return get_object(Genome, session, genome_id) | {"id": id}

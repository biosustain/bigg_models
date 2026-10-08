from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, subqueryload
from cobradb.models import (
    Annotation,
    AnnotationLink,
    Component,
    ComponentAnnotationMapping,
    ComponentReferenceMapping,
    Reaction,
    ReactionAnnotationMapping,
    ReactionMatrix,
    ReferenceCompound,
    ReferenceCompoundAnnotationMapping,
    ReferenceReaction,
    ReferenceReactionAnnotationMapping,
    UniversalComponent,
    UniversalReaction,
    UniversalReactionMatrix,
)


def extract_reaction_participants(matrix):
    participants = []
    for m in matrix:
        bigg_id = m.compartmentalized_component.bigg_id
        coefficient = m.universal_reaction_matrix.coefficient
        participants.append((coefficient, bigg_id))
    return participants


def extract_universal_reaction_participants(matrix):
    participants = []
    for m in matrix:
        bigg_id = m.universal_compartmentalized_component.bigg_id
        coefficient = m.coefficient
        participants.append((coefficient, bigg_id))
    return participants


def extract_cross_references(annotation_db, source_type, match):
    """List the external identifiers linked by one annotation, with provenance.

    source is the annotation the identifiers come from, and source_type how
    that annotation is linked to the entity: through its reference (Rhea
    reaction or ChEBI compound), or through ModelSEED matching. match records
    how the link was established (see the data access page).
    """
    return [
        {
            "namespace": link.data_source.bigg_id,
            "identifier": link.identifier,
            "source": annotation_db.bigg_id,
            "source_type": source_type,
            "source_obsolete": annotation_db.is_obsolete,
            "match": match,
        }
        for link in annotation_db.links
    ]


def unique_cross_references(cross_references):
    unique = []
    for x in cross_references:
        if x not in unique:
            unique.append(x)
    return unique


def get_match_flags(mapping_db, flags):
    return [name for attr, name in flags if getattr(mapping_db, attr)]


REACTION_MATCH_FLAGS = [("bigg_id_match", "bigg_id"), ("pattern_match", "stoichiometry")]
METABOLITE_MATCH_FLAGS = [("bigg_id_match", "bigg_id"), ("inchi_match", "inchikey")]


def get_reactions(session: Session):
    annotation_options = joinedload(
        ReferenceReactionAnnotationMapping.annotation
    ).subqueryload(Annotation.links).joinedload(AnnotationLink.data_source)
    query = select(Reaction)
    query = query.options(
        joinedload(Reaction.universal_reaction).options(
            joinedload(UniversalReaction.reference)
            .subqueryload(ReferenceReaction.annotation_mappings)
            .options(annotation_options),
            subqueryload(UniversalReaction.old_bigg_ids),
            subqueryload(UniversalReaction.matrix).joinedload(
                UniversalReactionMatrix.universal_compartmentalized_component
            ),
        ),
        subqueryload(Reaction.matrix).options(
            joinedload(ReactionMatrix.compartmentalized_component),
            joinedload(ReactionMatrix.universal_reaction_matrix),
        ),
        subqueryload(Reaction.annotation_mappings)
        .joinedload(ReactionAnnotationMapping.annotation)
        .subqueryload(Annotation.links)
        .joinedload(AnnotationLink.data_source),
    )
    query = query.filter(Reaction.collection_id == None)
    results = session.scalars(query).all()

    reactions = []
    for reaction_db in results:
        d = {
            "bigg_id": reaction_db.bigg_id,
            "copy_number": reaction_db.copy_number,
            "participants": extract_reaction_participants(reaction_db.matrix),
            "universalreaction__bigg_id": reaction_db.universal_reaction.bigg_id,
            "universalreaction__name": reaction_db.universal_reaction.name,
            "universalreaction__participants": extract_universal_reaction_participants(
                reaction_db.universal_reaction.matrix
            ),
            "universalreaction__is_exchange": reaction_db.universal_reaction.is_exchange,
            "universalreaction__is_pseudo": reaction_db.universal_reaction.is_pseudo,
            "universalreaction__is_transport": reaction_db.universal_reaction.is_transport,
            "universalreaction__old_bigg_ids": [
                x.old_bigg_id for x in reaction_db.universal_reaction.old_bigg_ids
            ],
        }
        cross_references = []
        if (reference_db := reaction_db.universal_reaction.reference) is not None:
            d["referencereaction__bigg_id"] = reference_db.bigg_id
            for mapping_db in reference_db.annotation_mappings:
                cross_references.extend(
                    extract_cross_references(
                        mapping_db.annotation, "rhea_reference", ["reference"]
                    )
                )
        for mapping_db in reaction_db.annotation_mappings:
            cross_references.extend(
                extract_cross_references(
                    mapping_db.annotation,
                    "modelseed",
                    get_match_flags(mapping_db, REACTION_MATCH_FLAGS),
                )
            )
        d["cross_references"] = unique_cross_references(cross_references)
        reactions.append(d)
    return reactions


def get_metabolites(session: Session):
    query = select(Component)
    query = query.options(
        joinedload(Component.universal_component).options(
            subqueryload(UniversalComponent.default_component),
            subqueryload(UniversalComponent.old_bigg_ids),
        ),
        subqueryload(Component.reference_mappings)
        .joinedload(ComponentReferenceMapping.reference_compound)
        .subqueryload(ReferenceCompound.annotation_mappings)
        .joinedload(ReferenceCompoundAnnotationMapping.annotation)
        .subqueryload(Annotation.links)
        .joinedload(AnnotationLink.data_source),
        subqueryload(Component.annotation_mappings)
        .joinedload(ComponentAnnotationMapping.annotation)
        .subqueryload(Annotation.links)
        .joinedload(AnnotationLink.data_source),
        subqueryload(Component.compartmentalized_components),
    )
    query = query.filter(Component.collection_id == None)
    results = session.scalars(query).all()

    metabolites = []
    for component_db in results:
        d = {
            "bigg_id": component_db.bigg_id,
            "name": component_db.name,
            "formula": component_db.formula,
            "charge": component_db.charge,
            "universalcomponent__bigg_id": component_db.universal_component.bigg_id,
            "universalcomponent__name": component_db.universal_component.name,
            "universalcomponent__default_component": component_db.universal_component.default_component.bigg_id,
            "universalcomponent__old_bigg_ids": [
                x.old_bigg_id for x in component_db.universal_component.old_bigg_ids
            ],
            "compartmentalized_components": [
                x.bigg_id for x in component_db.compartmentalized_components
            ],
            "references": [
                x.reference_compound.bigg_id for x in component_db.reference_mappings
            ],
        }
        cross_references = []
        for reference_mapping_db in component_db.reference_mappings:
            for mapping_db in reference_mapping_db.reference_compound.annotation_mappings:
                cross_references.extend(
                    extract_cross_references(
                        mapping_db.annotation, "chebi_reference", ["reference"]
                    )
                )
        for mapping_db in component_db.annotation_mappings:
            cross_references.extend(
                extract_cross_references(
                    mapping_db.annotation,
                    "modelseed",
                    get_match_flags(mapping_db, METABOLITE_MATCH_FLAGS),
                )
            )
        d["cross_references"] = unique_cross_references(cross_references)
        metabolites.append(d)
    return metabolites

from sqlalchemy.orm import (
    aliased,
    contains_eager,
    selectinload,
    subqueryload,
    joinedload,
    Session,
)
from biggr_models.handlers.utils import format_bigg_id
from biggr_models.queries import utils
from cobradb.models import (
    Annotation,
    AnnotationLink,
    ModelReactionEscherMapping,
    ReferenceReactionAnnotationMapping,
    Compartment,
    CompartmentalizedComponent,
    UniversalCompartmentalizedComponent,
    Component,
    ComponentReferenceMapping,
    UniversalComponent,
    Gene,
    GeneReactionMatrix,
    Model,
    ModelGene,
    ModelReaction,
    Reaction,
    ReactionAnnotationMapping,
    ReactionMatrix,
    ReferenceReaction,
    ReferenceReactionParticipant,
    ReferenceCompound,
    UniversalReaction,
    UniversalReactionMatrix,
)
from cobradb.parse import split_id_and_copy_tag
from sqlalchemy import func, asc, select
from typing import Any, Dict

from biggr_models.queries.memote_queries import get_memote_results_for_reaction
from biggr_models.queries.metabolite_queries import process_annotation_for_template


def get_universal_reactions_count(session):
    """Return the number of universal reactions."""
    return session.scalars(
        select(func.count(UniversalReaction.id)).filter(
            UniversalReaction.collection_id == None
        )
    ).first()


def get_universal_reactions(
    session,
    page=None,
    size=None,
    sort_column=None,
    sort_direction="ascending",
    **kwargs,
):
    """Get universal reactions.

    Arguments
    ---------

    session: An ome session object.

    page: The page, or None for all pages.

    size: The page length, or None for all pages.

    sort_column: The name of the column to sort. Must be one of 'bigg_id', 'name'.

    sort_direction: Either 'ascending' or 'descending'.

    Returns
    -------

    A list of objects with keys 'bigg_id', 'name'.

    """
    # get the sort column
    columns = {
        "bigg_id": func.lower(UniversalReaction.bigg_id),
        "name": func.lower(UniversalReaction.name),
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
    query = select(UniversalReaction.bigg_id, UniversalReaction.name).filter(
        UniversalReaction.collection_id == None
    )

    # order and limit
    query = utils._apply_order_limit_offset(
        query, sort_column_object, sort_direction, page, size
    )

    query = session.execute(query)
    return [{"bigg_id": x[0], "name": x[1]} for x in query]


def get_model_reactions_count(model_bigg_id, session):
    """Count the model reactions."""
    return session.scalars(
        select(func.count(Reaction.id))
        .join(ModelReaction, ModelReaction.reaction_id == Reaction.id)
        .join(Model, Model.id == ModelReaction.model_id)
        .filter(Model.bigg_id == model_bigg_id)
    ).first()


def get_model_reactions(
    model_bigg_id,
    session,
    page=None,
    size=None,
    sort_column=None,
    sort_direction="ascending",
    **kwargs,
):
    """Get model reactions.

    Arguments
    ---------

    model_bigg_id: The bigg id of the model to retrieve reactions.

    session: An ome session object.

    page: The page, or None for all pages.

    size: The page length, or None for all pages.

    sort_column: The name of the column to sort. Must be one of 'bigg_id', 'name',
    'model_bigg_id', and 'organism'.

    sort_direction: Either 'ascending' or 'descending'.

    Returns
    -------

    A list of objects with keys 'bigg_id', 'name', 'model_bigg_id', and
    'organism'.

    """
    # get the sort column
    columns = {
        "bigg_id": func.lower(UniversalReaction.bigg_id),
        "name": func.lower(UniversalReaction.name),
        "model_bigg_id": func.lower(Model.bigg_id),
        "organism": func.lower(Model.organism),
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
    query = (
        select(
            UniversalReaction.bigg_id,
            UniversalReaction.name,
            Model.bigg_id,
            Model.organism,
            ModelReaction.copy_number,
        )
        .join(Reaction, Reaction.universal_reaction_id == UniversalReaction.id)
        .join(ModelReaction, ModelReaction.reaction_id == Reaction.id)
        .join(Model, Model.id == ModelReaction.model_id)
        .filter(Model.bigg_id == model_bigg_id)
    )

    # order and limit
    query = utils._apply_order_limit_offset(
        query, sort_column_object, sort_direction, page, size
    )

    query = session.execute(query)
    return [
        {
            "bigg_id": f"{x[0]}:{x[4]}" if x[4] != 1 else x[0],
            "name": x[1],
            "model_bigg_id": x[2],
            "organism": x[3],
        }
        for x in query
    ]


def _get_metabolite_and_reference_list_for_reaction(reaction_id, session):
    cr = aliased(ComponentReferenceMapping)
    cr_id = cr.id.label("cr_id")
    subq = (
        select(cr_id).filter(cr.component_id == Component.id).limit(1).scalar_subquery()
    )
    result_db = session.execute(
        select(
            CompartmentalizedComponent.bigg_id,
            Component.bigg_id,
            UniversalReactionMatrix.coefficient,
            Compartment.bigg_id,
            Component.name,
            ReferenceCompound,
            ComponentReferenceMapping,
            ReferenceReactionParticipant,
            ReactionMatrix.id,
        )
        .join(CompartmentalizedComponent.compartment)
        .join(
            Component,
            CompartmentalizedComponent.component_id == Component.id,
        )
        .join(
            ReactionMatrix,
            ReactionMatrix.compartmentalized_component_id
            == CompartmentalizedComponent.id,
        )
        .join(
            UniversalReactionMatrix,
            UniversalReactionMatrix.id == ReactionMatrix.universal_reaction_matrix_id,
        )
        .join(
            Reaction,
            Reaction.id == ReactionMatrix.reaction_id,
        )
        .join(UniversalReaction, UniversalReaction.id == Reaction.universal_reaction_id)
        .join(
            ReferenceReaction,
            ReferenceReaction.id == UniversalReaction.reference_id,
            isouter=True,
        )
        .join(
            ReferenceReactionParticipant,
            UniversalReactionMatrix.reference_reaction_participant_id
            == ReferenceReactionParticipant.id,
            isouter=True,
        )
        # .join(
        #     ComponentReferenceMapping,
        #     ComponentReferenceMapping.component_id == Component.id,
        #     isouter=True,
        # )
        .join(
            ComponentReferenceMapping,
            ComponentReferenceMapping.id == subq,
            isouter=True,
        )
        .join(
            ReferenceCompound,
            ReferenceCompound.id == ComponentReferenceMapping.reference_compound_id,
            isouter=True,
        )  # TODO: Does this work when there is no reference?
        .filter(Reaction.id == reaction_id)
        .order_by(
            asc(UniversalReactionMatrix.coefficient > 0),
            asc(CompartmentalizedComponent.bigg_id),
        )
    ).all()

    return [
        {
            "base_bigg_id": x[1],
            "bigg_id": x[0],
            "coefficient": x[2],
            "coefficient_int_or_float": int(x[2]) if x[2].is_integer() else x[2],
            "compartment_bigg_id": x[3],
            "name": x[4],
            "reference_mapping": x[6],
            "reference": x[5],
            "reference_participant": x[7],
        }
        for x in result_db
    ]


def get_universal_reaction_and_models(
    session: Session, reaction_bigg_id: str
) -> Dict[str, Any]:
    universal_reaction_db = session.scalars(
        select(UniversalReaction)
        .options(
            subqueryload(UniversalReaction.reactions).options(
                subqueryload(Reaction.matrix).options(
                    joinedload(ReactionMatrix.universal_reaction_matrix),
                    joinedload(ReactionMatrix.compartmentalized_component).joinedload(
                        CompartmentalizedComponent.compartment
                    ),
                ),
            ),
            joinedload(UniversalReaction.collection),
            joinedload(UniversalReaction.reference).options(
                subqueryload(
                    ReferenceReaction.universal_reactions.and_(
                        UniversalReaction.bigg_id != reaction_bigg_id
                    )
                ),
                subqueryload(ReferenceReaction.annotation_mappings)
                .joinedload(ReferenceReactionAnnotationMapping.annotation)
                .options(
                    subqueryload(Annotation.links).joinedload(
                        AnnotationLink.data_source
                    ),
                    subqueryload(Annotation.properties),
                ),
            ),
            subqueryload(UniversalReaction.matrix).options(
                joinedload(UniversalReactionMatrix.reference_reaction_participant),
                joinedload(
                    UniversalReactionMatrix.universal_compartmentalized_component
                ).options(
                    joinedload(UniversalCompartmentalizedComponent.compartment),
                    joinedload(UniversalCompartmentalizedComponent.universal_component)
                    .joinedload(UniversalComponent.default_component)
                    .subqueryload(Component.reference_mappings)
                    .joinedload(ComponentReferenceMapping.reference_compound),
                ),
            ),
        )
        .filter(UniversalReaction.bigg_id == reaction_bigg_id)
        .limit(1)
    ).first()
    if not universal_reaction_db:
        raise utils.NotFoundError("No Reaction found with BiGG ID " + reaction_bigg_id)

    all_annotations = []
    if universal_reaction_db.reference:
        all_annotations.extend(
            (
                process_annotation_for_template(annotation_mapping.annotation),
                annotation_mapping,
            )
            for annotation_mapping in universal_reaction_db.reference.annotation_mappings
        )
    all_annotations.extend(
        (
            process_annotation_for_template(annotation_mapping.annotation),
            annotation_mapping,
        )
        for reaction_db in universal_reaction_db.reactions
        for annotation_mapping in reaction_db.annotation_mappings
    )

    aligned_metabolite_ids = {"universal": ([], []), "urm": ([], [])}
    for urm in universal_reaction_db.matrix:
        aligned_metabolite_ids["universal"][int(urm.coefficient > 0)].append(urm.id)
        aligned_metabolite_ids["urm"][int(urm.coefficient > 0)].append(urm)

    for reaction_db in universal_reaction_db.reactions:
        aligned_metabolite_ids[reaction_db.id] = (
            [None] * len(aligned_metabolite_ids["universal"][0]),
            [None] * len(aligned_metabolite_ids["universal"][1]),
        )
        for rm in reaction_db.matrix:
            urm_id = rm.universal_reaction_matrix_id
            lr = int(rm.universal_reaction_matrix.coefficient > 0)
            if urm_id in aligned_metabolite_ids["universal"][lr]:
                aligned_metabolite_ids[reaction_db.id][lr][
                    aligned_metabolite_ids["universal"][lr].index(urm_id)
                ] = rm
            else:
                pos = None
                for i in range(len(aligned_metabolite_ids["universal"][lr])):
                    if aligned_metabolite_ids["universal"][lr][i] is not None:
                        continue
                    if aligned_metabolite_ids[reaction_db.id][lr][i] is not None:
                        continue
                    pos = i
                    break
                if pos is None:
                    for k in aligned_metabolite_ids.keys():
                        aligned_metabolite_ids[k][lr].append(None)
                    pos = -1
                aligned_metabolite_ids[reaction_db.id][lr][pos] = rm

    del aligned_metabolite_ids["universal"]
    aligned_reaction_strings = {}
    for k, v in aligned_metabolite_ids.items():
        l = []
        for lr in [0, 1]:
            prev_empty = True
            for rm in v[lr]:
                if rm is None:
                    l.append("")
                    continue
                if k == "urm":
                    formatted_bigg_id = format_bigg_id(
                        rm.universal_compartmentalized_component.bigg_id,
                        format_type="universal_comp_comp",
                    )
                else:
                    formatted_bigg_id = format_bigg_id(
                        rm.compartmentalized_component.bigg_id, format_type="comp_comp"
                    )

                coeff = ""
                if k == "urm":
                    m_coeff = rm.coefficient
                else:
                    m_coeff = rm.universal_reaction_matrix.coefficient
                if (m_coeff := abs(float(m_coeff))) != 1:
                    if m_coeff.is_integer():
                        m_coeff = int(m_coeff)
                    coeff = f"<span class='fw-bold'>{coeff}</span> "
                prefix = "" if prev_empty else "+ "

                s = f"{prefix}{coeff}{formatted_bigg_id}"
                l.append(s)
                prev_empty = False
            if lr == 0:
                l.append(" &#8652; ")
        aligned_reaction_strings[k] = l

    annotation_sources = []
    annotation_properties = {}
    annotation_links = {}
    for annotation, _ in all_annotations:
        for k, vs in annotation["properties"].items():
            if k not in annotation_properties:
                annotation_properties[k] = {}
            for v in vs:
                if v not in annotation_properties[k]:
                    annotation_properties[k][v] = set()
                source = (annotation["type"], annotation["identifier"])
                if source not in annotation_sources:
                    annotation_sources.append(source)
                annotation_properties[k][v].add(annotation_sources.index(source))
        for k, vs in annotation["links"].items():
            if k not in annotation_links:
                annotation_links[k] = {}
            for v in vs:
                if v["value"] not in annotation_links[k]:
                    annotation_links[k][v["value"]] = (v["url"], set())
                source = (annotation["type"], annotation["identifier"])
                if source not in annotation_sources:
                    annotation_sources.append(source)
                annotation_links[k][v["value"]][1].add(annotation_sources.index(source))

    return {
        "universal_reaction": universal_reaction_db,
        "reference": universal_reaction_db.reference,
        "all_annotations": all_annotations,
        "aligned_reactions": aligned_reaction_strings,
        "annotation_sources": annotation_sources,
        "annotation_properties": annotation_properties,
        "annotation_linkouts": annotation_links,
    }


def get_reactions_for_model(model_bigg_id, session):
    result_db = session.execute(
        select(Reaction.bigg_id, Reaction.name, Model.organism)
        .join(ModelReaction, ModelReaction.reaction_id == Reaction.id)
        .join(Model, Model.id == ModelReaction.model_id)
        .filter(Model.bigg_id == model_bigg_id)
    ).all()
    return [{"bigg_id": x[0], "name": x[1], "organism": x[2]} for x in result_db]


def _get_gene_list_for_model_reaction(model_reaction_id, session):
    result_db = session.execute(
        select(Gene.bigg_id, Gene.name)
        .join(Gene.model_genes)
        .join(ModelGene.reaction_matrix)
        .filter(GeneReactionMatrix.model_reaction_id == model_reaction_id)
    )
    return [{"bigg_id": x[0], "name": x[1]} for x in result_db]


def get_model_list_for_reaction(reaction_bigg_id, session):
    result = session.scalars(
        select(Model.bigg_id)
        .join(ModelReaction, ModelReaction.model_id == Model.id)
        .join(Reaction, Reaction.id == ModelReaction.reaction_id)
        .join(Reaction.universal_reaction)
        .filter(UniversalReaction.bigg_id == reaction_bigg_id)
        .distinct()
    ).all()
    return [{"bigg_id": x[0]} for x in result]


def get_reference_for_reaction(reaction_bigg_id, session):
    ur_alias = aliased(UniversalReaction)
    result = session.scalars(
        select(ReferenceReaction)
        .options(
            subqueryload(
                ReferenceReaction.universal_reactions.and_(
                    UniversalReaction.bigg_id != reaction_bigg_id,
                    UniversalReaction.collection_id == None,
                )
            )
        )
        .execution_options(populate_existing=True)
        .join(ur_alias, ur_alias.reference_id == ReferenceReaction.id)
        .filter(ur_alias.bigg_id == reaction_bigg_id)
        .limit(1)
    ).first()
    return result


def get_model_reaction(model_bigg_id, biggr_id, session):
    """Get details about this reaction in the given model. Returns multiple
    results when the reaction appears in the model multiple times.

    """

    reaction_bigg_id, copy_number = split_id_and_copy_tag(biggr_id)
    full_bigg_id = (
        reaction_bigg_id if copy_number == 1 else f"{reaction_bigg_id}:{copy_number}"
    )

    model_reaction_db = session.scalars(
        select(ModelReaction)
        .options(
            contains_eager(ModelReaction.reaction).contains_eager(
                Reaction.universal_reaction
            ),
            contains_eager(ModelReaction.model),
            subqueryload(ModelReaction.escher_mappings).joinedload(
                ModelReactionEscherMapping.escher_module
            ),
        )
        .join(ModelReaction.reaction)
        .join(Reaction.universal_reaction)
        .join(ModelReaction.model)
        .filter(Model.bigg_id == model_bigg_id)
        .filter(ModelReaction.copy_number == copy_number)
        .filter(UniversalReaction.bigg_id == reaction_bigg_id)
        .limit(1)
    ).first()
    if model_reaction_db is None:
        raise utils.NotFoundError(
            "Reaction %s not found in model %s" % (reaction_bigg_id, model_bigg_id)
        )

    # metabolites
    metabolite_db = _get_metabolite_and_reference_list_for_reaction(
        model_reaction_db.reaction_id, session
    )

    # models
    model_db = get_model_list_for_reaction(reaction_bigg_id, session)
    model_result = [x for x in model_db if x != model_bigg_id]

    # reference
    reference_db = get_reference_for_reaction(reaction_bigg_id, session)

    all_annotations = []
    if reference_db is not None:
        ref_ann = session.execute(
            select(Annotation, ReferenceReactionAnnotationMapping)
            .options(
                selectinload(Annotation.properties),
                selectinload(Annotation.links).joinedload(AnnotationLink.data_source),
            )
            .join(Annotation.reference_reaction_mappings)
            .filter(
                ReferenceReactionAnnotationMapping.reference_reaction_id
                == reference_db.id
            )
            .join(ReferenceReactionAnnotationMapping.reference_reaction)
        ).all()
        if ref_ann:
            ref_annotations = [
                (process_annotation_for_template(ann), ann_map)
                for ann, ann_map in ref_ann
            ]
            all_annotations.extend(ref_annotations)

    reaction_ann = session.execute(
        select(Annotation, ReactionAnnotationMapping)
        .options(
            selectinload(Annotation.properties),
            selectinload(Annotation.links).joinedload(AnnotationLink.data_source),
        )
        .join(Annotation.reaction_mappings)
        .filter(ReactionAnnotationMapping.reaction_id == model_reaction_db.reaction_id)
    ).all()
    if reaction_ann:
        reaction_annotations = [
            (process_annotation_for_template(ann), ann_map)
            for ann, ann_map in reaction_ann
        ]
        all_annotations.extend(reaction_annotations)

    annotation_sources = []
    annotation_properties = {}
    annotation_links = {}
    for annotation, _ in all_annotations:
        for k, vs in annotation["properties"].items():
            if k not in annotation_properties:
                annotation_properties[k] = {}
            for v in vs:
                if v not in annotation_properties[k]:
                    annotation_properties[k][v] = set()
                source = (annotation["type"], annotation["identifier"])
                if source not in annotation_sources:
                    annotation_sources.append(source)
                annotation_properties[k][v].add(annotation_sources.index(source))
        for k, vs in annotation["links"].items():
            if k not in annotation_links:
                annotation_links[k] = {}
            for v in vs:
                if v["value"] not in annotation_links[k]:
                    annotation_links[k][v["value"]] = (v["url"], set())
                source = (annotation["type"], annotation["identifier"])
                if source not in annotation_sources:
                    annotation_sources.append(source)
                annotation_links[k][v["value"]][1].add(annotation_sources.index(source))

    all_other_copy_numbers = session.scalars(
        select(ModelReaction.copy_number)
        .join(Reaction, Reaction.id == ModelReaction.reaction_id)
        .filter(
            Reaction.universal_reaction_id
            == model_reaction_db.reaction.universal_reaction_id
        )
        .filter(ModelReaction.model_id == model_reaction_db.model_id)
        .filter(ModelReaction.copy_number != model_reaction_db.copy_number)
    ).all()
    other_copy_numbers = list(sorted(x for x in all_other_copy_numbers))

    # # old identifiers
    # old_id_results = id_queries._get_old_ids_for_model_reaction(
    #     model_bigg_id, reaction_bigg_id, session
    # )

    gene_db = _get_gene_list_for_model_reaction(model_reaction_db.id, session)
    reaction_string = utils.build_reaction_string(
        metabolite_db,
        model_reaction_db.lower_bound,
        model_reaction_db.upper_bound,
        False,
        format_met="comp_comp",
    )
    memote_result_db = get_memote_results_for_reaction(session, model_reaction_db.id)

    return {
        "bigg_id": reaction_bigg_id,
        "full_bigg_id": full_bigg_id,
        "model_bigg_id": model_bigg_id,
        "model": model_reaction_db.model,
        "reaction": model_reaction_db.reaction,
        "all_annotations": all_annotations,
        "model_reaction": model_reaction_db,
        "universal_reaction": model_reaction_db.reaction.universal_reaction,
        "other_copy_numbers": other_copy_numbers,
        "reaction_string": reaction_string,
        "memote_result": memote_result_db,
        "genes": gene_db,
        "reference": reference_db,
        "other_models_with_reaction": model_result,
        "metabolites": metabolite_db,
        "annotation_sources": annotation_sources,
        "annotation_properties": annotation_properties,
        "annotation_linkouts": annotation_links,
    }


def get_reaction(reaction_bigg_id, session):
    return session.scalars(
        select(Reaction).filter(Reaction.bigg_id == reaction_bigg_id).limit(1)
    ).first()


REF_ANNOTATIONS_SUBQ = (
    subqueryload(ReferenceReaction.annotation_mappings)
    .subqueryload(ReferenceReactionAnnotationMapping.annotation)
    .options(subqueryload(Annotation.properties), subqueryload(Annotation.links))
)
REACTION_ANNOTATIONS_SUBQ = (
    subqueryload(Reaction.annotation_mappings)
    .subqueryload(ReactionAnnotationMapping.annotation)
    .options(subqueryload(Annotation.properties), subqueryload(Annotation.links))
)


def get_reaction_object(
    session: Session, id: utils.IDType, load_annotations: bool = True
) -> Dict[str, Any]:
    if not isinstance(load_annotations, bool):
        return None

    id_sel = utils.convert_id_to_query_filter(id, Reaction)
    reaction_db = session.scalars(
        select(Reaction)
        .options(
            joinedload(Reaction.collection),
            subqueryload(Reaction.matrix).joinedload(
                ReactionMatrix.compartmentalized_component
            ),
            subqueryload(Reaction.universal_reaction)
            .joinedload(UniversalReaction.reference)
            .options(
                subqueryload(ReferenceReaction.reaction_participants).joinedload(
                    ReferenceReactionParticipant.compound
                ),
                *((REF_ANNOTATIONS_SUBQ,) if load_annotations else ()),
            ),
            *((REACTION_ANNOTATIONS_SUBQ,) if load_annotations else ()),
        )
        .filter(id_sel)
        .limit(1)
    ).first()

    if reaction_db is None:
        raise utils.NotFoundError(f"No Component found with BiGG ID {id}")

    return {"id": id, "object": reaction_db}

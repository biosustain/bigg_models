from sqlalchemy.orm import (
    contains_eager,
    joinedload,
    selectinload,
    subqueryload,
    Session,
)
from biggr_models.handlers import metabolite_handlers
from biggr_models.queries import utils
from typing import Any, Dict

from cobradb.models import (
    Annotation,
    AnnotationLink,
    ComponentIDMapping,
    ReferenceCompoundAnnotationMapping,
    ComponentAnnotationMapping,
    CompartmentalizedComponent,
    Component,
    ComponentReferenceMapping,
    ReferenceCompound,
    UniversalComponent,
    UniversalCompartmentalizedComponent,
    UniversalComponentReferenceMapping,
    Compartment,
    ModelCompartmentalizedComponent,
    Model,
    ReferenceReactivePartMatrix,
)
from cobradb.api import utils as api_utils

from sqlalchemy import func, or_, select

from biggr_models.queries.memote_queries import get_memote_results_for_metabolite

LINKOUT_PROPERTY_KEYS = {
    "name": "Names",
    "smiles": "SMILES",
    "mass": "Molecular Mass||g/mol",
}

ANNOTATION_TYPES = {
    "seed": "ModelSEED",
    "chebi": "ChEBI",
    "rhea": "RHEA",
}
REFERENCE_COMPOUND_TYPES = {
    "small_molecule": "Small Molecule",
    "generic_polypeptide": "Protein-linked Reactive Group",
    "generic_polynucleotide": "Polynucleotide-linked Reactive Group",
}


def get_universal_metabolites_count(session):
    return session.scalars(
        select(func.count(UniversalComponent.id)).filter(
            UniversalComponent.collection_id == None
        )
    ).first()


def get_universal_metabolites(
    session,
    page=None,
    size=None,
    sort_column=None,
    sort_direction="ascending",
    **kwargs,
):
    """Get universal metabolites.

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
        "bigg_id": func.lower(UniversalComponent.bigg_id),
        "name": func.lower(UniversalComponent.name),
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
    query = select(UniversalComponent.bigg_id, UniversalComponent.name).filter(
        UniversalComponent.collection_id == None
    )

    # order and limit
    query = utils._apply_order_limit_offset(
        query, sort_column_object, sort_direction, page, size
    )

    query = session.execute(query).all()
    return [{"bigg_id": x[0], "name": x[1]} for x in query]


def get_model_metabolites_count(model_bigg_id, session):
    """Count the model metabolites."""
    return session.scalars(
        select(func.count(ModelCompartmentalizedComponent.id))
        .join(ModelCompartmentalizedComponent.model)
        .filter(Model.bigg_id == model_bigg_id)
    ).first()


def get_model_metabolites(
    model_bigg_id,
    session,
    page=None,
    size=None,
    sort_column=None,
    sort_direction="ascending",
    **kwargs,
):
    """Get model metabolites.

    Arguments
    ---------

    model_bigg_id: The bigg id of the model to retrieve metabolites.

    session: An ome session object.

    page: The page, or None for all pages.

    size: The page length, or None for all pages.

    sort_column: The name of the column to sort. Must be one of 'bigg_id',
    'name', 'model_bigg_id', and 'organism'.

    sort_direction: Either 'ascending' or 'descending'.

    Returns
    -------

    A list of objects with keys 'bigg_id', 'name', 'compartment_bigg_id',
    'model_bigg_id', and 'organism'.

    """
    # get the sort column
    columns = {
        "bigg_id": [
            func.lower(CompartmentalizedComponent.bigg_id),
        ],
        "name": func.lower(Component.name),
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
            CompartmentalizedComponent.bigg_id,
            Component.name,
            Model.bigg_id,
            Model.organism,
            Compartment.bigg_id,
        )
        .join(
            Component,
            CompartmentalizedComponent.component_id == Component.id,
        )
        .join(
            ModelCompartmentalizedComponent,
            ModelCompartmentalizedComponent.compartmentalized_component_id
            == CompartmentalizedComponent.id,
        )
        .join(Model, Model.id == ModelCompartmentalizedComponent.model_id)
        .join(CompartmentalizedComponent.compartment)
        .filter(Model.bigg_id == model_bigg_id)
    )

    # order and limit
    query = utils._apply_order_limit_offset(
        query, sort_column_object, sort_direction, page, size
    )

    query = session.execute(query).all()
    return [
        {
            "bigg_id": x[0],
            "name": x[1],
            "model_bigg_id": x[2],
            "organism": x[3],
            "compartment_bigg_id": x[4],
        }
        for x in query
    ]


def process_annotation_for_template(ann: Annotation):
    d = {
        "id": ann.id,
        "bigg_id": ann.bigg_id,
        "identifier": (
            ann.bigg_id
            if ann.bigg_id.startswith("CHEBI:")
            else ann.bigg_id.split(":", maxsplit=1)[-1]
        ),
        "default_data_source_id": ann.default_data_source_id,
        "type": ANNOTATION_TYPES.get(ann.type, ann.type),
    }
    d_links = {}
    for link in ann.links:
        source_name = link.data_source.name
        d_link = {
            "value": link.identifier,
            "url": f"{link.data_source.url_prefix}{link.identifier}",
        }
        if source_name in d_links:
            d_links[source_name].append(d_link)
        else:
            d_links[source_name] = [d_link]
    d["links"] = d_links

    d_props = {}
    for prop in ann.properties:
        new_prop_key = LINKOUT_PROPERTY_KEYS.get(prop.key)
        if new_prop_key is None:
            continue
        if new_prop_key in d_props:
            d_props[new_prop_key].append(prop.value)
        else:
            d_props[new_prop_key] = [prop.value]
    d["properties"] = d_props
    return d


def get_metabolite(met_bigg_id, session):
    result_db = session.execute(
        select(UniversalComponent.bigg_id, UniversalComponent.name)
        .filter(UniversalComponent.bigg_id == met_bigg_id)
        .limit(1)
    ).first()
    if result_db is None:
        raise utils.NotFoundError("No Component found with BiGG ID " + met_bigg_id)
        # Look for a result with a deprecated ID
        # res_db = (
        #     session.query(DeprecatedID, UniversalComponent)
        #     .filter(DeprecatedID.type == "component")
        #     .filter(DeprecatedID.deprecated_id == met_bigg_id)
        #     .join(UniversalComponent, UniversalComponent.id == DeprecatedID.ome_id)
        #     .first()
        # )
        # if res_db:
        #     raise utils.RedirectError(res_db[1].bigg_id)
        # else:
        #     raise utils.NotFoundError("No Component found with BiGG ID " + met_bigg_id)

    comp_comp_db = session.execute(
        select(
            CompartmentalizedComponent.bigg_id,
            Model.bigg_id,
            Model.organism,
        )
        .join(
            UniversalCompartmentalizedComponent,
            CompartmentalizedComponent.universal_compartmentalized_component_id
            == UniversalCompartmentalizedComponent.id,
        )
        .join(
            ModelCompartmentalizedComponent,
            ModelCompartmentalizedComponent.compartmentalized_component_id
            == CompartmentalizedComponent.id,
        )
        .join(Model, Model.id == ModelCompartmentalizedComponent.model_id)
        .join(
            UniversalComponent,
            UniversalComponent.id
            == UniversalCompartmentalizedComponent.universal_component_id,
        )
        .filter(UniversalComponent.bigg_id == met_bigg_id)
    ).all()

    default_component_db = session.scalars(
        select(Component)
        .join(
            ComponentReferenceMapping,
            Component.id == ComponentReferenceMapping.component_id,
        )
        .join(
            UniversalComponentReferenceMapping,
            ComponentReferenceMapping.id
            == UniversalComponentReferenceMapping.mapping_id,
        )
        .join(UniversalComponentReferenceMapping.universal_component)
        .filter(UniversalComponent.bigg_id == met_bigg_id)
        .limit(1)
    ).first()
    default_component = None

    if default_component_db:
        default_component = {
            "bigg_id": default_component_db.bigg_id,
            "formula": default_component_db.formula,
            "charge": default_component_db.charge,
        }

    components_db = session.scalars(
        select(Component)
        .options(
            contains_eager(Component.universal_component),
            subqueryload(Component.reference_mappings)
            .joinedload(ComponentReferenceMapping.reference_compound)
            .options(
                joinedload(ReferenceCompound.inchi),
                subqueryload(ReferenceCompound.reactive_part_matrix).joinedload(
                    ReferenceReactivePartMatrix.reactive_part
                ),
            ),
        )
        .join(Component.universal_component)
        .filter(UniversalComponent.bigg_id == met_bigg_id)
        .order_by(Component.charge)
    ).all()

    components = []
    for component in components_db:
        references = []
        for ref_map_db in component.reference_mappings:
            ref = {
                "id": ref_map_db.reference_compound.id,
                "bigg_id": ref_map_db.reference_compound.bigg_id,
                "name": ref_map_db.reference_compound.name,
                "reference_n": ref_map_db.reference_n,
                "reference_formula_delta": (
                    None
                    if ref_map_db.reference_formula_delta is None
                    else api_utils.Formula(
                        ref_map_db.reference_formula_delta
                    ).grouped_str()
                ),
                "type": ref_map_db.reference_compound.compound_type,
                "type_str": REFERENCE_COMPOUND_TYPES.get(
                    ref_map_db.reference_compound.compound_type,
                    ref_map_db.reference_compound.compound_type,
                ),
                "charge": ref_map_db.reference_compound.charge,
                "formula": ref_map_db.reference_compound.formula,
                "inchi": ref_map_db.reference_compound.inchi,
                "reactive_parts": [
                    m.reactive_part
                    for m in ref_map_db.reference_compound.reactive_part_matrix
                ],
            }
            ref_ann = session.execute(
                select(Annotation, ReferenceCompoundAnnotationMapping)
                .options(
                    selectinload(Annotation.properties),
                    selectinload(Annotation.links).joinedload(
                        AnnotationLink.data_source
                    ),
                )
                .join(Annotation.reference_compound_mappings)
                .filter(
                    ReferenceCompoundAnnotationMapping.reference_compound_id
                    == ref_map_db.reference_compound.id
                )
                .join(ReferenceCompoundAnnotationMapping.reference_compound)
            ).all()
            if ref_ann:
                ref["annotations"] = [
                    (process_annotation_for_template(ann), ann_map)
                    for ann, ann_map in ref_ann
                ]
            references.append(ref)

        comp_ann = session.execute(
            select(Annotation, ComponentAnnotationMapping)
            .options(
                selectinload(Annotation.properties),
                selectinload(Annotation.links).joinedload(AnnotationLink.data_source),
            )
            .join(Annotation.component_mappings)
            .filter(Annotation.is_obsolete == False)
            .filter(ComponentAnnotationMapping.component_id == component.id)
        ).all()

        d = {
            "id": component.id,
            "bigg_id": component.bigg_id,
            "name": component.name,
            "charge": component.charge,
            "formula": component.formula,
            "reference": references,
        }
        if comp_ann:
            d["annotations"] = [
                (process_annotation_for_template(ann), ann_map)
                for ann, ann_map in comp_ann
            ]
        if (
            default_component is not None
            and default_component["bigg_id"] == d["bigg_id"]
        ):
            d["default"] = True
            components.insert(0, d)
        else:
            components.append(d)

    for comp in components:
        all_annotations = []
        for ref in comp["reference"]:
            all_annotations.extend(ref.get("annotations", []))
        all_annotations.extend(comp.get("annotations", []))
        comp["all_annotations"] = all_annotations

    for comp in components:
        a_sources = []
        ap = {}
        al = {}
        for annotation, _ in comp["all_annotations"]:
            for k, vs in annotation["properties"].items():
                if k not in ap:
                    ap[k] = {}
                for v in vs:
                    if v not in ap[k]:
                        ap[k][v] = set()
                    source = (annotation["type"], annotation["identifier"])
                    if source not in a_sources:
                        a_sources.append(source)
                    ap[k][v].add(a_sources.index(source))
            for k, vs in annotation["links"].items():
                if k not in al:
                    al[k] = {}
                for v in vs:
                    if v["value"] not in al[k]:
                        al[k][v["value"]] = (v["url"], set())
                    source = (annotation["type"], annotation["identifier"])
                    if source not in a_sources:
                        a_sources.append(source)
                    al[k][v["value"]][1].add(a_sources.index(source))

        comp["annotation_properties"] = ap
        comp["annotation_linkouts"] = al
        comp["annotation_sources"] = a_sources

    metabolite_in_models_url = f"/universal/metabolite_in_models/{result_db[0]}"
    metabolite_in_models_columns = (
        metabolite_handlers.MetaboliteInModelsListViewHandler.column_specs
    )

    return {
        "bigg_id": result_db[0],
        "name": result_db[1],
        "components": components,
        "default_component": default_component,
        "compartments_in_models": [
            {"bigg_id": c[0], "model_bigg_id": c[1], "organism": c[2]}
            for c in comp_comp_db
        ],
        "metabolite_in_models_url": metabolite_in_models_url,
        "metabolite_in_models_columns": metabolite_in_models_columns,
    }


def get_model_list_for_metabolite(metabolite_bigg_id, session):
    result = session.execute(
        select(Model.bigg_id, CompartmentalizedComponent.compartment_id)
        .join(
            ModelCompartmentalizedComponent,
            ModelCompartmentalizedComponent.compartmentalized_component_id
            == CompartmentalizedComponent.id,
        )
        .join(Model, Model.id == ModelCompartmentalizedComponent.model_id)
        .join(CompartmentalizedComponent.component)
        .filter(Component.bigg_id == metabolite_bigg_id)
    )
    return [{"bigg_id": x[0], "compartment_bigg_id": x[1]} for x in result]


def get_model_comp_metabolite(comp_met_id, model_bigg_id, session):
    model_comp_comp_db = session.scalars(
        select(ModelCompartmentalizedComponent)
        .options(
            contains_eager(ModelCompartmentalizedComponent.model),
            contains_eager(ModelCompartmentalizedComponent.compartmentalized_component)
            .joinedload(CompartmentalizedComponent.component)
            .options(
                joinedload(Component.universal_component),
                subqueryload(Component.reference_mappings)
                .joinedload(ComponentReferenceMapping.reference_compound)
                .options(
                    joinedload(ReferenceCompound.inchi),
                    subqueryload(ReferenceCompound.reactive_part_matrix).joinedload(
                        ReferenceReactivePartMatrix.reactive_part
                    ),
                ),
            ),
        )
        .join(ModelCompartmentalizedComponent.model)
        .join(ModelCompartmentalizedComponent.compartmentalized_component)
        .filter(Model.bigg_id == model_bigg_id)
        .filter(
            or_(
                ModelCompartmentalizedComponent.bigg_id == comp_met_id,
                CompartmentalizedComponent.bigg_id == comp_met_id,
            )
        )
        .limit(1)
    ).first()
    if model_comp_comp_db is None:
        raise utils.NotFoundError(
            "Component %s not in model %s" % (comp_met_id, model_bigg_id)
        )
    references = []
    for (
        ref_map_db
    ) in model_comp_comp_db.compartmentalized_component.component.reference_mappings:
        if ref_map_db.reference_formula_delta is not None:
            print(api_utils.Formula(ref_map_db.reference_formula_delta).grouped_str())
        ref = {
            "id": ref_map_db.id,
            "reference_n": ref_map_db.reference_n,
            "reference_formula_delta": (
                None
                if ref_map_db.reference_formula_delta is None
                else api_utils.Formula(ref_map_db.reference_formula_delta).grouped_str()
            ),
            "bigg_id": ref_map_db.reference_compound.bigg_id,
            "name": ref_map_db.reference_compound.name,
            "type": ref_map_db.reference_compound.compound_type,
            "type_str": REFERENCE_COMPOUND_TYPES.get(
                ref_map_db.reference_compound.compound_type,
                ref_map_db.reference_compound.compound_type,
            ),
            "charge": ref_map_db.reference_compound.charge,
            "formula": ref_map_db.reference_compound.formula,
            "inchi": ref_map_db.reference_compound.inchi,
            "reactive_parts": [
                m.reactive_part
                for m in ref_map_db.reference_compound.reactive_part_matrix
            ],
        }
        ref_ann = session.execute(
            select(Annotation, ReferenceCompoundAnnotationMapping)
            .options(
                selectinload(Annotation.properties),
                selectinload(Annotation.links).joinedload(AnnotationLink.data_source),
            )
            .join(Annotation.reference_compound_mappings)
            .filter(
                ReferenceCompoundAnnotationMapping.reference_compound_id
                == ref_map_db.reference_compound.id
            )
            .join(ReferenceCompoundAnnotationMapping.reference_compound)
        ).all()
        if ref_ann:
            ref["annotations"] = [
                (process_annotation_for_template(ann), ann_map)
                for ann, ann_map in ref_ann
            ]

        references.append(ref)

    model_db = get_model_list_for_metabolite(
        model_comp_comp_db.compartmentalized_component.component.bigg_id, session
    )
    model_result = [x for x in model_db if x["bigg_id"] != model_bigg_id]

    comp_ann = session.execute(
        select(Annotation, ComponentAnnotationMapping)
        .options(
            selectinload(Annotation.properties),
            selectinload(Annotation.links).joinedload(AnnotationLink.data_source),
        )
        .join(Annotation.component_mappings)
        .filter(
            ComponentAnnotationMapping.component_id
            == model_comp_comp_db.compartmentalized_component.component.id
        )
    ).all()

    comp_ann = [
        (process_annotation_for_template(ann), ann_map) for ann, ann_map in comp_ann
    ]
    all_ann = []
    for ref in references:
        if (ref_ann := ref.get("annotations")) is not None:
            all_ann.extend(ref_ann)
    all_ann.extend(comp_ann)

    annotation_sources = []
    annotation_properties = {}
    annotation_links = {}
    for annotation, _ in all_ann:
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

    memote_result_db = get_memote_results_for_metabolite(session, model_comp_comp_db.id)

    metabolite_in_reactions_url = f"/models/{model_comp_comp_db.model.bigg_id}/metabolite_in_reactions/{model_comp_comp_db.bigg_id}"
    metabolite_in_reactions_columns = (
        metabolite_handlers.MetaboliteInReactionsListViewHandler.column_specs
    )

    return {
        "bigg_id": model_comp_comp_db.bigg_id,
        "model_comp_comp": model_comp_comp_db,
        "comp_comp": model_comp_comp_db.compartmentalized_component,
        "compartment": model_comp_comp_db.compartmentalized_component.compartment,
        "component": model_comp_comp_db.compartmentalized_component.component,
        "universal_component": model_comp_comp_db.compartmentalized_component.component.universal_component,
        "model": model_comp_comp_db.model,
        # "reactions": [
        #     {"bigg_id": r[0], "name": r[1], "model_bigg_id": r[2]} for r in reactions_db
        # ],
        "other_models_with_metabolite": model_result,
        "references": references,
        "all_annotations": all_ann,
        "annotation_sources": annotation_sources,
        "annotation_properties": annotation_properties,
        "annotation_linkouts": annotation_links,
        "metabolite_in_reactions_url": metabolite_in_reactions_url,
        "metabolite_in_reactions_columns": metabolite_in_reactions_columns,
        "memote_result": memote_result_db,
    }


REF_ANNOTATIONS_SUBQ = (
    subqueryload(ReferenceCompound.annotation_mappings)
    .subqueryload(ReferenceCompoundAnnotationMapping.annotation)
    .options(
        subqueryload(Annotation.properties),
        subqueryload(Annotation.links).joinedload(AnnotationLink.data_source),
    )
)
COMP_ANNOTATIONS_SUBQ = (
    subqueryload(Component.annotation_mappings)
    .subqueryload(ComponentAnnotationMapping.annotation)
    .options(
        subqueryload(Annotation.properties),
        subqueryload(Annotation.links).joinedload(AnnotationLink.data_source),
    )
)


def get_component_object(
    session: Session, id: utils.IDType, load_annotations: bool = True
) -> Dict[str, Any]:
    if not isinstance(load_annotations, bool):
        return None

    id_sel = utils.convert_id_to_query_filter(id, Component)
    component_db = session.scalars(
        select(Component)
        .options(
            subqueryload(Component.universal_component),
            subqueryload(Component.model),
            subqueryload(Component.compartmentalized_components).subqueryload(
                CompartmentalizedComponent.compartment
            ),
            subqueryload(Component.reference_mappings)
            .subqueryload(ComponentReferenceMapping.reference_compound)
            .options(
                subqueryload(ReferenceCompound.inchi),
                *((REF_ANNOTATIONS_SUBQ,) if load_annotations else ()),
            ),
            *((COMP_ANNOTATIONS_SUBQ,) if load_annotations else ()),
        )
        .filter(id_sel)
        .limit(1)
    ).first()

    if component_db is None:
        raise utils.NotFoundError(f"No Component found with BiGG ID {id}")

    return {"id": id, "object": component_db}


def get_universal_component_object(
    session, id: utils.IDType, load_annotations: bool = True
):
    if not isinstance(load_annotations, bool):
        return None

    id_sel = utils.convert_id_to_query_filter(id, UniversalComponent)
    universal_component_db = session.scalars(
        select(UniversalComponent)
        .options(
            subqueryload(UniversalComponent.components).options(
                joinedload(Component.model),
                subqueryload(Component.compartmentalized_components).subqueryload(
                    CompartmentalizedComponent.compartment
                ),
                subqueryload(Component.reference_mappings)
                .joinedload(ComponentReferenceMapping.reference_compound)
                .options(
                    joinedload(ReferenceCompound.inchi),
                    *((REF_ANNOTATIONS_SUBQ,) if load_annotations else ()),
                ),
                *((COMP_ANNOTATIONS_SUBQ,) if load_annotations else ()),
            )
        )
        .filter(id_sel)
        .limit(1)
    ).first()

    if universal_component_db is None:
        raise utils.NotFoundError(f"No UniversalComponent found with BiGG ID {id}")

    return {"id": id, "object": universal_component_db}


def get_compartmentalized_component_object(
    session, id: utils.IDType, load_annotations: bool = True
):
    if not isinstance(load_annotations, bool):
        return None

    id_sel = utils.convert_id_to_query_filter(id, CompartmentalizedComponent)
    comp_component_db = session.scalars(
        select(CompartmentalizedComponent)
        .options(
            subqueryload(CompartmentalizedComponent.compartment),
            subqueryload(CompartmentalizedComponent.component).options(
                subqueryload(Component.universal_component),
                subqueryload(Component.model),
                subqueryload(Component.reference_mappings)
                .subqueryload(ComponentReferenceMapping.reference_compound)
                .options(
                    subqueryload(ReferenceCompound.inchi),
                    *((REF_ANNOTATIONS_SUBQ,) if load_annotations else ()),
                ),
                *((COMP_ANNOTATIONS_SUBQ,) if load_annotations else ()),
            ),
        )
        .filter(id_sel)
        .limit(1)
    ).first()

    if comp_component_db is None:
        raise utils.NotFoundError(
            f"No CompartmentalizedComponent found with BiGG ID {id}"
        )

    return {"id": id, "object": comp_component_db}


def get_model_compartmentalized_component_object(
    session,
    id: utils.IDType,
    model_id: utils.IDType,
    load_annotations: bool = True,
):
    if not isinstance(load_annotations, bool):
        return None

    id_sel = utils.convert_id_to_query_filter(id, CompartmentalizedComponent)
    model_sel = utils.convert_id_to_query_filter(model_id, Model)
    comp_component_db = session.scalars(
        select(ModelCompartmentalizedComponent)
        .join(ModelCompartmentalizedComponent.compartmentalized_component)
        .join(ModelCompartmentalizedComponent.model)
        .join(CompartmentalizedComponent.compartment)
        .join(CompartmentalizedComponent.component)
        .join(Component.universal_component)
        .options(
            contains_eager(ModelCompartmentalizedComponent.model),
            contains_eager(
                ModelCompartmentalizedComponent.compartmentalized_component
            ).options(
                contains_eager(CompartmentalizedComponent.compartment),
                contains_eager(CompartmentalizedComponent.component).options(
                    contains_eager(Component.universal_component),
                    subqueryload(Component.reference_mappings)
                    .joinedload(ComponentReferenceMapping.reference_compound)
                    .options(
                        joinedload(ReferenceCompound.inchi),
                        *((REF_ANNOTATIONS_SUBQ,) if load_annotations else ()),
                    ),
                    *((COMP_ANNOTATIONS_SUBQ,) if load_annotations else ()),
                ),
            ),
        )
        .filter(id_sel & model_sel)
        .limit(1)
    ).first()

    if comp_component_db is None:
        raise utils.NotFoundError(
            f"No ModelCompartmentalizedComponent found with BiGG ID {id} and model BiGG ID {model_id}"
        )

    return {
        "id": id,
        "model_id": model_id,
        "object": comp_component_db,
    }


def get_any_components_by_identifiers(
    session: Session, identifiers: utils.StrList, model_bigg_id: utils.OptStr = None
):
    model = None
    if model_bigg_id is not None:
        model = session.scalars(
            select(Model).filter(Model.bigg_id == model_bigg_id).limit(1)
        ).first()
    if model is None:
        model_sel = lambda x: (x.collection_id == None)
    else:
        model_sel = lambda x: (
            (x.collection_id == None) | (x.collection_id == model.collection_id)
        )
    ignored_identifiers = []
    results = {}
    for full_identifier in identifiers:
        if not ":" in full_identifier:
            ignored_identifiers.append(full_identifier)
            continue
        namespace, identifier = full_identifier.split(":", maxsplit=1)
        idf = identifier
        namespace = namespace.upper()
        if namespace == "BIGGR" or namespace == "BIGG":
            charge = None
            if ":" in idf:
                idf, charge = idf.rsplit(":", maxsplit=1)
            compartment = None
            if idf[-2] == "_":
                compartment = idf[-1]
                idf = idf[:-2]
            universal_component_db = session.scalars(
                select(UniversalComponent)
                .join(UniversalComponent.old_bigg_ids)
                .filter(ComponentIDMapping.old_bigg_id == idf)
                .limit(1)
            ).first()
            if universal_component_db is None:
                universal_component_db = session.scalars(
                    select(UniversalComponent)
                    .filter(UniversalComponent.bigg_id == idf)
                    .filter(model_sel(UniversalComponent))
                    .limit(1)
                ).first()
            if universal_component_db is None:
                results[full_identifier] = None
                continue
            if charge is None and compartment is None:
                results[full_identifier] = universal_component_db
                continue
            if charge is None:
                universal_compartmentalized_component_db = session.scalars(
                    select(UniversalCompartmentalizedComponent)
                    .filter(
                        UniversalCompartmentalizedComponent.bigg_id
                        == f"{idf}_{compartment}"
                    )
                    .limit(1)
                ).first()
                if universal_compartmentalized_component_db is None:
                    results[full_identifier] = None
                    continue
                results[full_identifier] = universal_compartmentalized_component_db
                continue
            if compartment is None:
                component_db = session.scalars(
                    select(Component)
                    .filter(Component.bigg_id == f"{idf}:{charge}")
                    .limit(1)
                ).first()
                if component_db is None:
                    results[full_identifier] = None
                    continue
                results[full_identifier] = component_db
                continue
            compartmentalized_component_db = session.scalars(
                select(CompartmentalizedComponent)
                .filter(
                    CompartmentalizedComponent.bigg_id
                    == f"{idf}_{compartment}:{charge}"
                )
                .limit(1)
            ).first()
            if compartmentalized_component_db is None:
                results[full_identifier] = None
                continue
            results[full_identifier] = compartmentalized_component_db
            continue
        if namespace == "CHEBI":
            component_db = session.scalars(
                select(Component)
                .join(Component.reference_mappings)
                .join(ComponentReferenceMapping.reference_compound)
                .filter(ReferenceCompound.bigg_id == f"CHEBI:{identifier}")
            ).first()
            if component_db is None:
                results[full_identifier] = None
                continue
            results[full_identifier] = component_db
            continue
    return results

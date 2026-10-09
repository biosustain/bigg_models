from functools import reduce
import operator
from typing import Dict, List, NewType, Optional, Type, Union

from sqlalchemy.orm import Session
from biggr_models.version import __version__ as version, __api_version__ as api_version
import biggr_models.handlers.utils as handler_utils

from cobradb.models import (
    Base,
    DatabaseVersion,
    Gene,
    Model,
    ModelGene,
)

from sqlalchemy import func, literal, or_, select
from os.path import abspath, dirname, join
from sqlalchemy.sql import functions as sql_functions

root_directory = abspath(join(dirname(__file__), ".."))

IDType = NewType("IDType", Union[str, int])
StrList = NewType("StrList", List[str])
OptStr = NewType("OptStr", Optional[str])


class NotFoundError(Exception):
    pass


class RedirectError(Exception):
    pass


def get_list(
    session: Session,
    column_specs: List["handler_utils.DataColumnSpec"],
    start: int = 0,
    length: Optional[int] = None,
    search_value: str = "",
    search_regex: bool = False,
    pre_filter=None,
    post_filter=None,
):
    joins = {}
    for y in column_specs:
        for x in y.requires:
            if (x_str := str(x)) not in joins:
                joins[x_str] = x
    query = select(*(x.agg_func(x.prop) for x in column_specs))
    for x in joins.values():
        query = query.join(x, isouter=True)
    if pre_filter is not None:
        query = pre_filter(query)
    count_query = query
    if post_filter is not None:
        count_query = post_filter(count_query)
    total_count = session.scalar(
        select(func.count()).select_from(count_query.subquery())
    )

    applied_filters = False
    # Global search
    search_value = search_value.strip()
    if search_value != "":
        applied_filters = True
        query = query.filter(
            or_(
                *(
                    func.lower(x.prop).contains(search_value.lower(), autoescape=True)
                    for x in column_specs
                    if x.global_search
                )
            )
        )
    # Column searches
    for col_spec in column_specs:
        changed, query = col_spec.search(query)
        applied_filters = applied_filters or changed

    if applied_filters:
        filtered_count = session.scalar(
            select(func.count()).select_from(query.subquery())
        )
    else:
        filtered_count = total_count

    # Ordering
    for i in range(len(column_specs)):
        try:
            col_spec = next(x for x in column_specs if x.order_priority == i)
        except StopIteration:
            break
        if col_spec.order_asc:
            query = query.order_by(col_spec.prop)
        else:
            query = query.order_by(col_spec.prop.desc())

    if post_filter is not None:
        query = post_filter(query)

    if start > 0:
        query = query.offset(start)
    if length is not None:
        query = query.limit(length)

    raw_result = session.execute(query).all()
    result = [
        {
            col_spec.identifier: col_spec.process(col_data)
            for col_spec, col_data in zip(column_specs, row)
        }
        for row in raw_result
    ]

    return result, total_count, filtered_count


def get_search_list(
    session: Session,
    search_query: Union[str, Dict[str, str]],
    column_specs: List["handler_utils.DataColumnSpec"],
    start: int = 0,
    length: Optional[int] = None,
    search_value: str = "",
    search_regex: bool = False,
    pre_filter=None,
    post_filter=None,
):
    subqueries = []
    main_prop = column_specs[0].prop

    for col_i, x in enumerate(column_specs):
        if x.score_modes is None:
            score_modes = ["startswith", "contains"]
        else:
            score_modes = x.score_modes
        # if x.search_query_exact_match:
        # score_modes = ["exact"]

        for score_mode_i, score_mode in enumerate(score_modes):
            if not x.apply_search_query:
                continue

            if isinstance(search_query, str):
                col_search_query = search_query
            else:
                col_search_query = search_query.get(x.identifier)
                if col_search_query is None:
                    continue

            score_i = score_mode_i * len(column_specs) + col_i
            cte_query = select(
                main_prop.label("score_id"),
                sql_functions.sum(literal(10 ** (-score_i))).label("score"),
            )
            for y in x.requires:
                if isinstance(y, tuple):
                    cte_query = cte_query.join(*y)
                else:
                    cte_query = cte_query.join(y)

            if x.search_query_remove_namespace:
                if ":" in col_search_query:
                    _, col_search_query = col_search_query.split(":", maxsplit=1)

            # lower() LIKE instead of ILIKE, so the lower() trigram indexes are used
            if score_mode == "startswith":
                cte_query = cte_query.filter(
                    func.lower(x.prop).startswith(
                        col_search_query.lower(), autoescape=True
                    )
                )
            elif score_mode == "contains":
                cte_query = cte_query.filter(
                    func.lower(x.prop).contains(
                        col_search_query.lower(), autoescape=True
                    )
                )
            else:
                cte_query = cte_query.filter(x.prop == col_search_query)

            cte_query = cte_query.group_by("score_id")
            cte_query = cte_query.subquery()
            subqueries.append(cte_query)
            score_i += 1

    score_query = select(
        reduce(sql_functions.coalesce, (x.c.score_id for x in subqueries)).label(
            "score_id"
        ),
        reduce(
            operator.add, (sql_functions.coalesce(x.c.score, 0) for x in subqueries)
        ).label("score"),
    )
    for x in subqueries[1:]:
        score_query = score_query.outerjoin_from(
            subqueries[0], x, subqueries[0].c.score_id == x.c.score_id, full=True
        )
    score_query = score_query.subquery()

    joins = {}
    for y in column_specs:
        for x in y.requires:
            if (x_str := str(x)) not in joins:
                joins[x_str] = x
    score_label = func.max(score_query.c.score).label("score")
    query = select(*([x.agg_func(x.prop) for x in column_specs] + [score_label]))
    for x in joins.values():
        if isinstance(x, tuple):
            query = query.join(*x, isouter=True)
        else:
            query = query.join(x, isouter=True)
    query = query.join(score_query, score_query.c.score_id == main_prop)
    if pre_filter is not None:
        query = pre_filter(query)
    count_query = query
    if post_filter is not None:
        count_query = post_filter(count_query)
    total_count = session.scalar(
        select(func.count()).select_from(count_query.subquery())
    )

    applied_filters = False
    # Global search
    search_value = search_value.strip()
    if search_value != "":
        applied_filters = True
        query = query.filter(
            or_(
                *(
                    func.lower(x.prop).contains(search_value.lower(), autoescape=True)
                    for x in column_specs
                    if x.global_search
                )
            )
        )
    # Column searches
    for col_spec in column_specs:
        changed, query = col_spec.search(query)
        applied_filters = applied_filters or changed

    if applied_filters:
        filt_query = query
        if post_filter is not None:
            filt_query = post_filter(filt_query)
        filtered_count = session.scalar(
            select(func.count()).select_from(filt_query.subquery())
        )
    else:
        filtered_count = total_count

    # Ordering
    for i in range(len(column_specs)):
        try:
            col_spec = next(x for x in column_specs if x.order_priority == i)
        except StopIteration:
            break
        if col_spec.order_asc:
            query = query.order_by(col_spec.prop)
        else:
            query = query.order_by(col_spec.prop.desc())

    query = query.order_by(score_label.desc())

    if post_filter is not None:
        query = post_filter(query)

    if start > 0:
        query = query.offset(start)
    if length is not None:
        query = query.limit(length)

    raw_result = session.execute(query).all()
    result = [
        {
            col_spec.identifier: col_spec.process(col_data)
            for col_spec, col_data in zip(column_specs, row)
        }
        for row in raw_result
    ]

    return result, total_count, filtered_count


def get_gene_list_for_model(model_bigg_id, session):
    result = (
        session.query(Gene.bigg_id, Gene.name, Model.organism, Model.bigg_id)
        .join(ModelGene, ModelGene.gene_id == Gene.id)
        .join(Model, Model.id == ModelGene.model_id)
        .filter(Model.bigg_id == model_bigg_id)
    )
    return [
        {"bigg_id": x[0], "name": x[1], "organism": x[2], "model_bigg_id": x[3]}
        for x in result
    ]


# -----------
# Utilities
# -----------


def build_reaction_string(
    metabolite_list,
    lower_bound,
    upper_bound,
    universal=False,
    html=True,
    format_met=None,
):
    reaction_string_parts = [[], []]
    for met in metabolite_list:
        part_i = int(float(met["coefficient"]) > 0)
        formatted_bigg_id = handler_utils.format_bigg_id(
            met["bigg_id"], format_type=format_met
        )
        if abs(float(met["coefficient"])) != 1:
            coeff = float(abs(met["coefficient"]))
            if coeff.is_integer():
                coeff = int(coeff)
            reaction_string_parts[part_i].append(
                f"<span class='fw-bold'>{coeff}</span> {formatted_bigg_id}"
            )
        else:
            reaction_string_parts[part_i].append(formatted_bigg_id)

    both_arrow = " &#8652; " if html else " <-> "
    left_arrow = " &#x2190; " if html else " <-- "
    right_arrow = " &#x2192; " if html else " --> "

    if len(metabolite_list) == 1 or universal is True:
        arrow = both_arrow
    elif lower_bound < 0 and upper_bound <= 0:
        arrow = left_arrow
    elif lower_bound >= 0 and upper_bound > 0:
        arrow = right_arrow
    else:
        arrow = both_arrow
    reaction_string = arrow.join(" + ".join(x) for x in reaction_string_parts)
    return reaction_string


# version


def database_version(session):
    return {
        "last_updated": str(session.query(DatabaseVersion).first().date_time),
        "biggr_models_version": version,
        "api_version": api_version,
    }


def convert_id_to_query_filter(bigg_id: IDType, obj_cls: Type[Base]):
    if isinstance(bigg_id, int):
        return obj_cls.id == bigg_id
    if isinstance(bigg_id, str):
        return obj_cls.bigg_id == bigg_id
    raise ValueError()

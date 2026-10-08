from json import JSONDecodeError
from typing import Type
from cobradb.models import (
    Annotation,
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
    Publication,
    Reaction,
    ReferenceCompound,
    ReferenceReaction,
    ReferenceReactivePart,
    Taxon,
    UniversalComponent,
    UniversalReaction,
)
import inspect
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session
import tornado
from tornado.web import HTTPError

from biggr_models.handlers import utils
from biggr_models.queries import (
    metabolite_queries,
    object_queries,
    utils as query_utils,
)


def object_type_variant(obj_type: Type[Base], int_id_only: bool = False):

    if int_id_only:
        idtype = int
    else:
        idtype = query_utils.IDType

    def wrapper(session: Session, id: idtype):
        return object_queries.get_object(obj_type, session, id)

    return wrapper


def object_property_variant(property, obj_type: Type[Base]):
    parent_obj_type = property.class_

    # print(f"{str(property.property)}: {obj_type.__name__}")

    def wrapper(session: Session, id: int):
        return object_queries.get_object_property(
            parent_obj_type, obj_type, property, session, id
        )

    return wrapper


MODELS_CLASS_MAP = {
    "MODEL": object_type_variant(Model),
    "COMPONENT": object_type_variant(Component),
    "COMPARTMENTALIZEDCOMPONENT": object_type_variant(CompartmentalizedComponent),
    "MODELCOMPARTMENTALIZEDCOMPONENT": metabolite_queries.get_model_compartmentalized_component_object,
    "MODELREACTION": object_queries.get_model_reaction_object,
    "UNIVERSALCOMPONENT": object_type_variant(UniversalComponent),
    "REACTION": object_type_variant(Reaction),
    "UNIVERSALREACTION": object_type_variant(UniversalReaction),
    "REFERENCEREACTION": object_type_variant(ReferenceReaction),
    "REFERENCECOMPOUND": object_type_variant(ReferenceCompound),
    "REFERENCEREACTIVEPART": object_type_variant(ReferenceReactivePart),
    "GENOME": object_type_variant(Genome, int_id_only=True),
    "CHROMOSOME": object_type_variant(Chromosome, int_id_only=True),
    "COMPARTMENT": object_type_variant(Compartment),
    "PUBLICATION": object_type_variant(Publication, int_id_only=True),
    "INCHI": object_type_variant(InChI, int_id_only=True),
    "MEMOTETEST": object_type_variant(MemoteTest),
    "MEMOTERESULT": object_type_variant(MemoteResult, int_id_only=True),
    "ANNOTATION": object_type_variant(Annotation),
    "TAXON": object_type_variant(Taxon, int_id_only=True),
}

MODELS_ALLOWED_PROPERTIES = []


def _add_all_relationship_properties():
    for model_cls in Base.__subclasses__():
        insp = sqlalchemy_inspect(model_cls)
        for k, v in insp.relationships.items():
            MODELS_ALLOWED_PROPERTIES.append((getattr(model_cls, k), v.mapper.entity))


_add_all_relationship_properties()
MODELS_PROPERTY_MAP = {
    str(x.property).upper().replace("_", ""): object_property_variant(x, y)
    for x, y in MODELS_ALLOWED_PROPERTIES
}

MODELS_MAP = MODELS_CLASS_MAP | MODELS_PROPERTY_MAP


def parse_id_type(x):
    if isinstance(x, (int, str)):
        return x
    raise ValueError()


def parse_strlist(x):
    return [str(y) for y in x]


def parse_optstr(x):
    if x is None:
        return None
    return str(x)


REQUEST_PARAMETER_TYPES = {
    "str": str,
    "bool": bool,
    "int": int,
    "float": float,
    "IDType": parse_id_type,
    "StrList": parse_strlist,
    "OptStr": parse_optstr,
}


def determine_query_signature(f):
    s = inspect.signature(f)
    args = []
    kwargs = []
    for p in s.parameters.values():
        if p.name == "session":
            continue
        annotation = str(p.annotation.__name__)
        if annotation not in REQUEST_PARAMETER_TYPES:
            raise ValueError(
                f"Query type annotation not valid for {str(f)}: {annotation}"
            )
        if p.default == inspect.Parameter.empty:
            args.append((p.name, annotation))
        else:
            kwargs.append((p.name, annotation))
    return dict(f=f, args=args, kwargs=kwargs)


MODELS_SIGNATURE = {k: determine_query_signature(v) for k, v in MODELS_MAP.items()}


class ObjectHandler(utils.BaseHandler):
    def post(self):
        try:
            data = tornado.escape.json_decode(self.request.body)
        except JSONDecodeError:
            raise HTTPError(status_code=400, reason="Invalid JSON request.")
        obj_type = data.get("type")
        if not obj_type:
            raise HTTPError(
                status_code=400,
                reason="object type not valid",
            )
        obj_type = str(obj_type).upper().replace("_", "")
        if not obj_type in MODELS_SIGNATURE:
            raise HTTPError(
                status_code=400,
                reason="object type not valid",
            )

        f_sign = MODELS_SIGNATURE[obj_type]

        args = []
        for arg_name, arg_type in f_sign["args"]:
            if arg_name not in data:
                raise HTTPError(
                    status_code=400,
                    reason=f"Not a valid request, parameter {arg_name} required.",
                )
            try:
                val = REQUEST_PARAMETER_TYPES[arg_type](data[arg_name])
            except:
                raise HTTPError(
                    status_code=400,
                    reason=f"Could not convert parameter {arg_name} to type {arg_type}.",
                )
            args.append(val)
        kwargs = {}
        for kwarg_name, kwarg_type in f_sign["kwargs"]:
            if kwarg_name not in data:
                continue
            try:
                val = REQUEST_PARAMETER_TYPES[kwarg_type](data[kwarg_name])
            except:
                raise HTTPError(
                    status_code=400,
                    reason=f"Could not convert parameter {kwarg_name} to type {kwarg_type}.",
                )
            kwargs[kwarg_name] = val

        result = utils.do_safe_query(MODELS_MAP[obj_type], *args, **kwargs)
        self.return_result(result)

from datetime import datetime
from operator import itemgetter
import re
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    # Protocol,
    Tuple,
    TypeVar,
    Union,
)
from cobradb.models import Base, Session
from sqlalchemy import Row, and_, or_
from sqlalchemy.sql.expression import Select
from biggr_models.queries import utils as query_utils
import json
from tornado.web import (
    RequestHandler,
    StaticFileHandler,
    HTTPError,
)

from jinja2 import Environment, PackageLoader
from os import path
import mimetypes
from pprint import pprint


MODELS_CLASS_MAP = {x.__name__: x for x in Base.__subclasses__()}


class BiGGrJSONEncoder(json.JSONEncoder):
    """Handle exporting database entities to the BiGGr API return format."""

    def default(self, o):
        if o is None:
            return None
        if isinstance(o, Row):
            return o._tuple()
        # if isinstance(o, (MemoteTest, MemoteResult)):
        #     print(vars(o))
        #     print(dir(o))
        #     print(o._to_shallow_dict())
        #     return o._to_shallow_dict()
        if isinstance(o, Base):
            return o._to_shallow_dict()
        if isinstance(o, datetime):
            return {"_type": "datetime", "iso": o.isoformat()}
        # Let the base class default method raise the TypeError
        return super().default(o)


def biggr_json_object_hook(o):
    """Hook function to use with JSONDecoder and cobradb objects."""
    if o is None:
        return None
    if not isinstance(o, dict):
        return o
    if "_type" not in o:
        return o
    if o["_type"] == "datetime":
        if isoformat := o.get("iso"):
            return datetime.fromisoformat(isoformat)
        else:
            return None
    if o["_type"] in MODELS_CLASS_MAP:
        model_class = MODELS_CLASS_MAP[o["_type"]]
        return model_class._from_dict(o)

    return None


def format_bigg_id(bigg_id: str, format_type: Optional[str] = None) -> str:
    """Generate a HTML string that formats any BiGG ID.

    The output results in accentuation of important parts of the BiGG ID.

    Parameters
    ----------
    bigg_id: str
        Input BiGG ID to format.
    format_type: str, optional
        The object type represented by the BiGG ID. Determines the exact
        formatting used. If format_type is None, no formatting is applied.
        Argument can be any of: 'comp' (Component), 'comp_comp'
        (CompartmentalizedComponent), 'universal_comp_comp'
        (UniversalCompartmentalizedComponent), 'reaction' (Reaction).

    Returns
    -------
    str
        HTML string containing formatted BiGG ID.
    """
    if format_type is None:
        return bigg_id
    try:
        prefix = ""
        if bigg_id.startswith("__"):
            if "__" in bigg_id[2:]:
                model_id, bigg_id = bigg_id[2:].split("__", maxsplit=1)
                prefix = (
                    "<span class='small opacity-75 fw-lighter'>"
                    f"__{model_id}__</span>"
                )
        if format_type == "comp_comp":
            comp_id, charge = bigg_id.rsplit(":", maxsplit=1)
            universal_id, compartment_id = comp_id.rsplit("_", maxsplit=1)
            return (
                f"{prefix}"
                f'<span class="fw-semibold">{universal_id}</span>'
                f'<span class="fw-normal opacity-75">'
                f"_{compartment_id}</span>"
                f'<span class="fw-normal fst-italic opacity-75 small">'
                f":{charge}</span>"
            )
        elif format_type == "comp":
            universal_id, charge = bigg_id.rsplit(":", maxsplit=1)
            return (
                f"{prefix}"
                f'<span class="fw-semibold">{universal_id}</span>'
                f'<span class="fw-normal fst-italic opacity-75 small">'
                f":{charge}</span>"
            )
        elif format_type == "universal_comp_comp":
            universal_id, compartment_id = bigg_id.rsplit("_", maxsplit=1)
            return (
                f"{prefix}"
                f'<span class="fw-semibold">{universal_id}</span>'
                f'<span class="fw-normal opacity-75">'
                f"_{compartment_id}</span>"
            )
        elif format_type == "reaction":
            if ":" in bigg_id:
                universal_id, copy_number = bigg_id.rsplit(":", maxsplit=1)
                return (
                    f"{prefix}"
                    f'<span class="fw-semibold">{universal_id}</span>'
                    f'<span class="fw-normal fst-italic opacity-75 small">'
                    f":{copy_number}</span>"
                )
            return f'{prefix}<span class="fw-semibold">{bigg_id}</span>'
        else:
            return bigg_id
    except:
        # Always fall back to simply returning the input BiGG ID.
        return bigg_id


def format_reference(identifier: str) -> str:
    """Format a reference identifier."""
    namespace, ref_id = identifier.split(":", maxsplit=1)
    return (
        f'<span class="fw-normal text-body-secondary">'
        f"{namespace}:</span>"
        f'<span class="text-body-emphasis">{ref_id}</span>'
    )


def format_gene_reaction_rule(grr: str) -> str:
    """Format a Gene Reaction Rule."""
    s = grr.replace("(", " ( ").replace(")", " ) ")
    s = [xs for x in s.split(" ") if (xs := x.strip()) != ""]
    s = [
        (
            x
            if x in [")", "(", "or", "and", "OR", "AND"]
            else f"<span class='fw-semibold'>{x}</span>"
        )
        for x in s
    ]
    res = " "
    for x in s:
        if x == ")" or res[-1] in " (":
            res = f"{res}{x}"
        else:
            res = f"{res} {x}"

    return res.strip()


# set up jinja2 template location
env = Environment(loader=PackageLoader("biggr_models", "templates"))
env.filters["format_reference"] = lambda x: format_reference(x)
env.filters["format_id"] = format_bigg_id
env.filters["format_gene_reaction_rule"] = format_gene_reaction_rule
env.filters["int_or_float"] = lambda x: int(x) if x.is_integer() else x

# root directory
directory = path.abspath(path.join(path.dirname(__file__), ".."))
static_model_dir = path.join(directory, "static", "models")


def safe_query(func, *args, **kwargs):
    session = Session()
    kwargs["session"] = session
    try:
        return func(*args, **kwargs)
    except query_utils.NotFoundError as e:
        raise HTTPError(status_code=404, reason=e.args[0])
    except ValueError as e:
        raise HTTPError(status_code=400, reason=e.args[0])
    finally:
        session.close()


# This type annotation is only available for python 3.12+
# rT = TypeVar("rT")
# class QueryProtocol[rT](Protocol):
#     def __call__(self, session: Session, *args, **kwargs) -> rT: ...
# def do_safe_query(func: QueryProtocol[rT], *args, **kwargs) -> rT:


def do_safe_query(func, *args, **kwargs):
    """Run the given function, and raise a 404 if it fails.

    Parameters
    ---------
    func: The function to run. A session object is passed as first argument to
    this function, *args and **kwargs are passed subsequently.

    Returns
    -------
    The result of `func`.

    Raises
    ------
    HTTPError
        Raises a 404 error if an entity was not found or 400 when a ValueError occurred.

    """
    session = Session()
    try:
        return func(session, *args, **kwargs)
    except query_utils.NotFoundError as e:
        raise HTTPError(status_code=404, reason=e.args[0])
    except ValueError as e:
        raise HTTPError(status_code=400, reason=e.args[0])
    finally:
        session.close()


class BaseHandler(RequestHandler):
    """Base RequestHandler that handles standard requests."""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def write(self, chunk):
        # note that serving a json list is a security risk
        # This is meant to be serving public-read only data only.
        if isinstance(chunk, (dict, list, tuple, Base)):
            try:
                value_str = json.dumps(chunk, cls=BiGGrJSONEncoder)
            except Exception as e:
                pprint(chunk)
                print(e)
            # value_str = json.dumps(chunk)
            RequestHandler.write(self, value_str)
            self.set_header("Content-type", "application/json; charset=utf-8")
        else:
            RequestHandler.write(self, chunk)

    def return_result(self, result=None):
        """Returns result as either rendered HTML or JSON

        This is suitable for cases where the template takes exactly the same
        result as the JSON api. This function will serve JSON if the request
        URI starts with JSON, otherwise it will render the objects template
        with the data

        """
        if self.request.uri.startswith("/api"):
            if result:
                if "breadcrumbs" in result:
                    del result["breadcrumbs"]

                self.write(result)
                self.finish()
            else:
                # For redirects
                pass
        else:
            if result:
                self.write(self.template.render(result))
                self.finish()
            else:
                self.write(self.template.render())
                self.finish()

    def get(self):
        self.return_result()


class TemplateHandler(BaseHandler):
    """Simple handler that only requires a template name."""

    def initialize(self, template_name):
        self.template = env.get_template(template_name)


def _interpret_bool(input: str) -> bool:
    return input.upper() == "TRUE"


def _interpret_asc(input: str) -> bool:
    return input.upper() == "ASC"


def col_str_search(query, col_spec: "DataColumn"):
    """Implements searching string columns in data tables.

    Searching is implemented as an icontains call, meaning that the query is filtered in
    a case-insensitive manner.

    Parameters
    ----------
    query: sqlalchemy query object
        Extra filters are added upon this query to achieve the search.
    col_spec: DataColumn
        All column information, including search query.

    Returns
    -------
    has_changed: bool
        True when any filter was applied to the query. Helps with optimizations.
    query
        The new query object.
    """
    if (search_value := col_spec.search_value.strip()) == "":
        return False, query
    return True, query.filter(col_spec.prop.icontains(search_value, autoescape=True))


def col_bool_search(query, col_spec: "DataColumn"):
    """Implements searching string columns in data tables.

    Searching is implemented as an icontains call, meaning that the query is filtered in
    a case-insensitive manner.

    Parameters
    ----------
    query: sqlalchemy query object
        Extra filters are added upon this query to achieve the search.
    col_spec: DataColumn
        All column information, including search query.

    Returns
    -------
    has_changed: bool
        True when any filter was applied to the query. Helps with optimizations.
    query
        The new query object.
    """
    if (search_value := col_spec.search_value.strip()) == "":
        return False, query
    value_as_bool = search_value.upper() == "TRUE"
    return True, query.filter(col_spec.prop == value_as_bool)


REGEX_COL_NUMBER_1 = re.compile(r"^((?P<eq>[\>\<]\=?) *)?(?P<nr>\d+(\.\d+)?)$")
REGEX_COL_NUMBER_2 = re.compile(r"^(?P<nr1>\d+(\.\d+)?) *\- *(?P<nr2>\d+(\.\d+)?)$")


def col_number_search(query: Select, col_spec: "DataColumn") -> Tuple[bool, Select]:
    """Implements searching number columns in data tables.

    Many number search patterns are implemented: >, <, >=, and <= can be used to search
    an open range, i.e. >10 will return all rows where the column value is greater than
    10. A closed inclusive range can be specified using a dash (-), i.e. 10-20 means 10
    up to and including 20. Commas (,) can be used to separate numbers and thus search
    for a list of numbers or a list of (open) ranges, effectively functioning as an OR
    operator. The ampersand symbol (&) can be used as an AND operator, e.g. >10&<20.

    Parameters
    ----------
    query: sqlalchemy query object
        Extra filters are added upon this query to achieve the search.
    col_spec: DataColumn
        All column information, including search query.

    Returns
    -------
    has_changed: bool
        True when any filter was applied to the query. Helps with optimizations.
    query
        The new query object.
    """
    if (search_value := col_spec.search_value.strip()) == "":
        return False, query

    or_filters = []
    for or_part in search_value.split(","):
        and_filters = []
        for and_part in or_part.split("&"):
            part = and_part.strip()
            m = REGEX_COL_NUMBER_1.match(part)
            if m is not None:
                print("Match 1")
                print(m.groups())
                number = float(m.group("nr"))
                try:
                    comp = m.group("eq")
                except IndexError:
                    comp = None
                if comp is None:
                    and_filters.append(col_spec.prop == number)
                else:
                    if comp == ">":
                        and_filters.append(col_spec.prop > number)
                    elif comp == ">=":
                        and_filters.append(col_spec.prop >= number)
                    elif comp == "<":
                        and_filters.append(col_spec.prop < number)
                    elif comp == "<=":
                        and_filters.append(col_spec.prop <= number)
                    else:
                        print(f"Fail 1: {comp}")
                        continue
                continue
            m = REGEX_COL_NUMBER_2.match(part)
            if m is not None:
                print("Match 2")
                number1 = float(m.group("nr1"))
                number2 = float(m.group("nr2"))
                and_filters.append(col_spec.prop >= number1)
                and_filters.append(col_spec.prop <= number2)
        if len(and_filters) == 1:
            or_filters.append(and_filters[0])
        elif len(and_filters) > 1:
            or_filters.append(and_(*and_filters))

    if len(or_filters) == 0:
        return False, query
    elif len(or_filters) == 1:
        return True, query.filter(or_filters[0])
    else:
        return True, query.filter(or_(*or_filters))


class DataColumnSpec:
    """This class holds all information of a data tables column."""

    def __init__(
        self,
        prop: Any,
        name: str,
        requires=None,
        agg_func=None,
        process=None,
        global_search: bool = True,
        hyperlink: Optional[str] = None,
        search_type: str = "str",
        apply_search_query: bool = True,
        score_modes: Optional[List[str]] = None,
        search_query_remove_namespace: bool = False,
        priority: Optional[int] = None,
        visible: bool = True,
    ):
        self.prop = prop
        self.identifier: str = str(prop).lower().replace(".", "__")
        self.name: str = name
        self.global_search = global_search
        self.requires: List[Any] = []
        if agg_func is None:
            self.agg_func = lambda x: x
        else:
            self.agg_func = agg_func
        if process is None:
            self.process = lambda x: x
        else:
            self.process = agg_func

        if isinstance(requires, Iterable):
            self.requires.extend(requires)
        elif requires is not None:
            self.requires.append(requires)

        self.search_type = search_type
        self.hyperlink = hyperlink
        self.apply_search_query = apply_search_query
        self.score_modes = score_modes
        self.search_query_remove_namespace = search_query_remove_namespace
        self.priority = priority  # DataTables.js responsive column priority
        self.visible = visible


class DataColumn:
    """This class adds user specified filters etc. on top of a DataColumnSpec."""

    def __init__(self, spec: DataColumnSpec):
        self.spec = spec
        self.search_value: str = ""
        self.order_priority: Optional[int] = None
        self.order_asc: bool = True
        self.search_regex: bool = False
        self.searchable: bool = True
        self.orderable: bool = True

    def __getattr__(self, name):
        return getattr(self.spec, name)

    def search(self, query):
        if self.search_value != "":
            print(f"{self.identifier}: '{self.search_value}' ({self.search_type})")
        if self.search_type == "str":
            return col_str_search(query, self)
        if self.search_type == "number":
            return col_number_search(query, self)
        if self.search_type == "bool":
            return col_bool_search(query, self)
        return False, query


def get_reverse_url(handler, name, path_kwargs):
    args = [
        (v, path_kwargs.get(k))
        for k, v in handler.application.wildcard_router.named_rules[
            name
        ].matcher.regex.groupindex.items()
    ]
    args = [
        "" if x is None else x
        for x in map(itemgetter(1), sorted(args, key=itemgetter(0)))
    ]
    url = handler.reverse_url(name, *args)
    url = url.replace("?/", "/")
    url = url.removesuffix("?")
    return url


_TT = TypeVar("_TT")
_TD = TypeVar("_TD")


class DataHandler(BaseHandler):
    """Request handler that implements data tables (API) logic."""

    template = env.get_template("data_table.html")
    title = None
    column_specs: List[DataColumnSpec] = []
    columns: List[DataColumn] = []
    start: int = 0
    length: Optional[int] = None
    draw: Optional[int] = None
    name = None
    search_value: str = ""
    search_regex: bool = False
    api: bool = False
    page_data: Optional[Dict[str, Any]] = None

    def initialize(self, **kwargs):
        self.columns = [DataColumn(col_spec) for col_spec in self.column_specs]
        self.name = kwargs.get("name")

    def breadcrumbs(self) -> Any:
        return None

    def pre_filter(self, query):
        return query

    def post_filter(self, query):
        return query

    def get(self, *args, **kwargs):
        if self.api:
            return self.return_data(*args, **kwargs)
        return self.return_page(*args, **kwargs)

    def return_page(self, *args, **kwargs):
        data = dict(
            data_url=self.data_url,
            columns=self.columns,
        )

        if self.page_data:
            data = data | self.page_data

        brcrmb = self.breadcrumbs()
        if brcrmb is not None:
            data["breadcrumbs"] = brcrmb

        if self.title is not None:
            data["title"] = self.title
        self.write(self.template.render(data))
        self.finish()

    def post(self, *args, **kwargs):
        return self.return_data(*args, **kwargs)

    def return_data(self, *args, **kwargs):
        data, total, filtered = self.data_query(query_utils.get_list)
        self.write_data(data, total, filtered)

    @property
    def data_url(self):
        if self.name is None:
            raise HTTPError(status_code=500, reason="Internal error, unnamed route.")

        # Resolve named groups, this is a bit of a workaround, since
        # reverse_url does not support named groups.
        return get_reverse_url(self, self.name, self.path_kwargs | {"api": "/api/v3"})

    def _get_argument_of_type_or_default(
        self, arg_name: str, arg_type: Callable[[Any], _TT], default: _TD = None
    ) -> Union[_TT, _TD]:
        arg_val = self.get_argument(arg_name, None)
        if arg_val is None:
            return default
        try:
            arg_val = arg_type(arg_val)
        except:
            return default
        return arg_val

    def _parse_data_tables_args(self):
        self.draw = self._get_argument_of_type_or_default("draw", int, None)
        self.start = self._get_argument_of_type_or_default("start", int, 0)
        self.length = self._get_argument_of_type_or_default("length", int, None)

        self.search_value = self._get_argument_of_type_or_default(
            "search[value]", str, ""
        )
        self.search_regex = self._get_argument_of_type_or_default(
            "search[regex]", _interpret_bool, False
        )

        for col_spec in self.columns:
            col_spec.order_priority = None
            col_spec.search_value = ""
        i = 0
        while (
            col_identifier := self.get_argument(f"columns[{i}][data]", None)
        ) is not None:
            if col_identifier == "x":
                i += 1
                continue
            try:
                col_spec = next(
                    x for x in self.columns if x.identifier == col_identifier
                )
            except StopIteration:
                raise HTTPError(
                    status_code=400,
                    reason="Could not parse datatables arguments.",
                )
            col_spec.searchable = self._get_argument_of_type_or_default(
                f"columns[{i}][searchable]", _interpret_bool, col_spec.searchable
            )
            col_spec.orderable = self._get_argument_of_type_or_default(
                f"columns[{i}][orderable]", _interpret_bool, col_spec.orderable
            )
            col_spec.search_value = self._get_argument_of_type_or_default(
                f"columns[{i}][search][value]", str, col_spec.search_value
            )
            col_spec.search_regex = self._get_argument_of_type_or_default(
                f"columns[{i}][search][regex]", _interpret_bool, col_spec.search_regex
            )

            i += 1

        i = 0
        while (
            col_identifier := self.get_argument(f"order[{i}][name]", None)
        ) is not None:
            if col_identifier == "x":
                i += 1
                continue
            try:
                col_spec = next(
                    x for x in self.columns if x.identifier == col_identifier
                )
            except StopIteration:
                raise HTTPError(
                    status_code=400,
                    reason="Could not parse datatables arguments.",
                )
            col_spec.order_priority = i
            col_spec.order_asc = self._get_argument_of_type_or_default(
                f"order[{i}][dir]", _interpret_asc, col_spec.order_asc
            )

            i += 1

    def prepare(self):
        for k, v in self.path_kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.api = self.path_kwargs.get("api") is not None
        if self.request.method == "POST" or self.api:
            self._parse_data_tables_args()

    def data_query(self, f, **kwargs):
        opts = dict(
            column_specs=self.columns,
            start=self.start,
            length=self.length,
            search_value=self.search_value,
            search_regex=self.search_regex,
            pre_filter=self.pre_filter,
            post_filter=self.post_filter,
        )
        opts = opts | kwargs
        results = do_safe_query(f, **opts)
        return results

    def write_data(self, data: Any, total_count: int, filtered_count: int):
        result = {
            "recordsTotal": total_count,
            "recordsFiltered": filtered_count,
            "data": data,
        }
        if self.draw is not None:
            result["draw"] = self.draw + 1
        self.write(result)
        self.finish()


class APIVersionHandler(BaseHandler):
    def get(self):
        result = safe_query(query_utils.database_version)
        self.return_result(result)


# static files
class StaticFileDownloadHandler(StaticFileHandler):
    def get_content_type(self):
        """Same as the default, but with utf8 encoding for XML and JSON files."""
        mime_type, encoding = mimetypes.guess_type(self.path)

        # from https://github.com/tornadoweb/tornado/pull/1468
        # per RFC 6713, use the appropriate type for a gzip compressed file
        if encoding is not None:
            return "application/octet-stream"

        # assume utf-8 for xml and json
        elif mime_type == "application/xml":
            return "application/xml; charset=utf-8"
        elif mime_type == "application/json":
            return "application/json; charset=utf-8"

        # from https://github.com/tornadoweb/tornado/pull/1468
        elif mime_type is not None:
            return mime_type
        # if mime_type not detected, use application/octet-stream
        else:
            return "application/octet-stream"

    def set_extra_headers(self, path: str) -> None:
        self.set_header("Content-Disposition", "attachment")


# static files
class StaticFileHandlerWithEncoding(StaticFileHandler):
    # This is only to opportunisticly use a pre-compressed file
    # (equivalent to gzip_static in nginx).
    def get_absolute_path(self, root, file_path):
        p = path.abspath(path.join(root, file_path))
        # if the client accepts gzip
        if "gzip" in self.request.headers.get("Accept-Encoding", ""):
            if path.isfile(p + ".gz"):
                self.set_header("Content-Encoding", "gzip")
                return p + ".gz"
        return p

    def get_content_type(self):
        """Same as the default, but with utf8 encoding for XML and JSON files."""
        mime_type, encoding = mimetypes.guess_type(self.path)

        # from https://github.com/tornadoweb/tornado/pull/1468
        # per RFC 6713, use the appropriate type for a gzip compressed file
        if encoding == "gzip":
            return "application/gzip"
        # As of 2015-07-21 there is no bzip2 encoding defined at
        # http://www.iana.org/assignments/media-types/media-types.xhtml
        # So for that (and any other encoding), use octet-stream.
        elif encoding is not None:
            return "application/octet-stream"

        # assume utf-8 for xml and json
        elif mime_type == "application/xml":
            return "application/xml; charset=utf-8"
        elif mime_type == "application/json":
            return "application/json; charset=utf-8"

        # from https://github.com/tornadoweb/tornado/pull/1468
        elif mime_type is not None:
            return mime_type
        # if mime_type not detected, use application/octet-stream
        else:
            return "application/octet-stream"

# -*- coding: utf-8 -*-
"""
ParsedInstance model utility functions
"""
import datetime
import json
from builtins import str as text
from typing import Any, Tuple

import six

from onadata.libs.utils.common_tags import DATE_FORMAT, MONGO_STRFTIME

KNOWN_DATES = ["_submission_time"]
NONE_JSON_FIELDS = {
    "_submission_time": "date_created",
    "_date_modified": "date_modified",
    "_id": "id",
    "_version": "version",
    "_last_edited": "last_edited",
}
OPERANDS = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=", "$i": "~*"}


def _json_sql_str(key, known_integers=None, known_dates=None, known_decimals=None):
    if known_integers is None:
        known_integers = []
    if known_dates is None:
        known_dates = []
    if known_decimals is None:
        known_decimals = []
    _json_str = "json->>%s"

    if key in known_integers:
        _json_str = "CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = "CAST(json->>%s AS TIMESTAMP)"
    elif key in known_decimals:
        _json_str = "CAST(json->>%s AS DECIMAL)"

    return _json_str


# pylint: disable=too-many-locals,too-many-branches
def _parse_where(query, known_integers, known_decimals, or_where, or_params):
    # using a dictionary here just incase we will need to filter using
    # other table columns
    where, where_params = [], []
    # pylint: disable=too-many-nested-blocks
    for (field_key, field_value) in six.iteritems(query):
        if isinstance(field_value, dict):
            if field_key in NONE_JSON_FIELDS:
                json_str = NONE_JSON_FIELDS.get(field_key)
            else:
                json_str = _json_sql_str(
                    field_key, known_integers, KNOWN_DATES, known_decimals
                )
            for (key, value) in six.iteritems(field_value):
                _v = None
                if key in OPERANDS:
                    where.append(" ".join([json_str, OPERANDS.get(key), "%s"]))
                _v = value
                if field_key in KNOWN_DATES:
                    raw_date = value
                    for date_format in (MONGO_STRFTIME, DATE_FORMAT):
                        try:
                            _v = datetime.datetime.strptime(raw_date[:19], date_format)
                        except ValueError:
                            pass
                if field_key in NONE_JSON_FIELDS:
                    where_params.extend([text(_v)])
                else:
                    where_params.extend((field_key, text(_v)))
        else:
            if field_key in NONE_JSON_FIELDS:
                where.append(f"{NONE_JSON_FIELDS[field_key]} = %s")
                where_params.append(text(field_value))
            elif field_value is None:
                where.append("json->>%s IS NULL")
                where_params.append(field_key)
            else:
                where.append("json->>%s = %s")
                where_params.extend((field_key, text(field_value)))

    return where + or_where, where_params + or_params


def _merge_duplicate_keys(pairs: Tuple[str, Any]):
    ret = {}

    for field, value in pairs:
        if not ret.get(field):
            ret[field] = []
        ret[field].append(value)

    for key, value in ret.items():
        if len(value) == 1:
            ret[key] = value[0]

    return ret


def get_where_clause(query, form_integer_fields=None, form_decimal_fields=None):
    """
    Returns where clause and related parameters.
    """
    if form_integer_fields is None:
        form_integer_fields = []
    if form_decimal_fields is None:
        form_decimal_fields = []
    known_integers = ["_id"] + form_integer_fields
    known_decimals = form_decimal_fields
    where = []
    where_params = []

    # pylint: disable=too-many-nested-blocks
    try:
        if query and isinstance(query, (dict, six.string_types)):
            query = (
                query
                if isinstance(query, dict)
                else json.loads(query, object_pairs_hook=_merge_duplicate_keys)
            )
            or_where = []
            or_params = []
            if isinstance(query, list):
                query = query[0]

            if isinstance(query, dict) and "$or" in list(query):
                or_dict = query.pop("$or")

                for or_query in or_dict:
                    for k, v in or_query.items():
                        if v is None:
                            or_where.extend([f"json->>'{k}' IS NULL"])
                        elif isinstance(v, list):
                            for value in v:
                                or_where.extend(["json->>%s = %s"])
                                or_params.extend([k, value])
                        else:
                            or_where.extend(["json->>%s = %s"])
                            or_params.extend([k, v])

                or_where = ["".join(["(", " OR ".join(or_where), ")"])]

            where, where_params = _parse_where(
                query, known_integers, known_decimals, or_where, or_params
            )

    except (ValueError, AttributeError) as e:
        if query and isinstance(query, six.string_types) and query.startswith("{"):
            raise e
        # cast query param to text
        where = ["json::text ~* cast(%s as text)"]
        where_params = [query]

    return where, where_params

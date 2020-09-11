import re
from typing import Dict, List, Set, Union
from urllib.parse import quote_plus, unquote_plus

from django.db.models.query import QuerySet
from django.http import QueryDict
from rest_framework import serializers

PATTERN = re.compile(r"\[(.*?)\]")


class QueryParameterField(serializers.BaseSerializer):
    default_error_messages = {
        "invalid": "Invalid parameter.",
        "not_related": "Does not represent a relationship.",
        "not_filterable": "Does not allow querystring operations like filtering or sorting.",
        "duplicate": "Can not specify parameter more than once.",
    }

    def __init__(self, serializer_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serializer_class = serializer_class

    def validate_key(self, key: str) -> str:
        """Validates and returns the query key."""
        return key

    def validate_value(self, value: str) -> str:
        """Validates and returns the query value."""
        return value

    def validate(self, querydict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validates and returns the entire query dictionary."""
        return querydict

    def represent_key(self, key: str) -> str:
        """Gets the representation of the query key."""
        return key

    def represent_value(self, value: str) -> str:
        """Gets the representation of the query value."""
        return value

    def represent(self, querydict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Gets the representation of the query dictionary."""
        return querydict

    def match_key(self, key: str) -> bool:
        """Determines whether the querystring key is a match to this field."""
        return False

    def extract_subkey(self, key: str) -> str:
        """Fetches the subkey from key.

        For example `foo[bar]` would return `bar`.
        """
        result = PATTERN.search(key)
        if result is None:
            return ""
        return result.group(1)

    def replace_subkey(self, key: str, repl: str) -> str:
        """Replaces the subkey in key.

        For example, replacing `bar` with `baz` in `foo[bar]`
        would result in `foo[baz]`.
        """
        return PATTERN.sub(repl, key, count=1)

    def validate_dotted_path(self, dotted_path: str, is_relationship: bool = False, is_filterable: bool = False) -> str:
        """Validates and inflects a dotted path to another serializer field.

        Args:
            dotted_path: The path to the serializer.
            is_relationship: Whether to validate that the final attribute is a relationship.
            is_filterable: Whether to validate that the final attribute is filterable.
        """
        inflected_path_chain = []
        field_names = dotted_path.split(".")
        serializer_class = self.serializer_class
        for field_name in field_names[:-1]:
            inflected_field_name = serializer_class.dja_get_inflection(field_name)
            inflected_path_chain.append(inflected_field_name)
            if not serializer_class.dja_is_relationship(inflected_field_name):
                self.fail("not_related")
            serializer_class = serializer_class.dja_get_relationship_serializer_class(inflected_field_name)
        inflected_field_name = serializer_class.dja_get_inflection(field_names[-1])
        inflected_path_chain.append(inflected_field_name)
        if is_relationship and not serializer_class.dja_is_relationship(inflected_field_name):
            self.fail("not_related")
        if is_filterable and not serializer_class.dja_is_filterable(inflected_field_name):
            self.fail("not_filterable")
        return ".".join(inflected_path_chain)

    def get_model_chain(self, validated_dotted_path: str) -> str:
        """Gets the "dunder" model path given by a dotted serializer path.

        Args:
            validated_dotted_path: A validated dotted path.
        """
        model_path_chain = []
        field_names = validated_dotted_path.split(".")
        serializer_class = self.serializer_class
        for field_name in field_names[:-1]:
            serializer_fields = serializer_class.dja_get_all_fields()
            serializer_field = serializer_fields[field_name]
            model_path_chain.extend(serializer_field.source.split("."))
            serializer_class = serializer_class.dja_get_relationship_serializer_class(field_name)
        return "__".join(model_path_chain)

    def represent_dotted_path(self, validated_dotted_path: str) -> str:
        """Gets the JSON:API inflection of a dotted serializer path.

        Args:
            validated_dotted_path: A validated dotted path.
        """
        inflected_data = ""
        serializer_class = self.serializer_class
        for field_name in validated_dotted_path.split("."):
            inflected_field_name = serializer_class.dja_get_inflection(field_name)
            inflected_data += inflected_field_name
            serializer_class = serializer_class.dja_get_relationship_serializer_class(field_name)
        return inflected_data

    def get_matched_keys(self, querydict: QueryDict) -> Set[str]:
        """Gets a set of keys applicable to this serializer."""
        matched_keys = set()
        for key in querydict:
            if self.match_key(key):
                matched_keys.add(key)
        return matched_keys

    def to_internal_value(self, querydict: QueryDict) -> Dict[str, List[str]]:
        """Inflect and validate the query dictionary."""
        matched_keys = self.get_matched_keys(querydict)
        out = {}
        for key in matched_keys:
            values = querydict.getlist(key)
            values = [unquote_plus(i).split(",") for i in values]
            values = [i for j in values for i in j]
            key = self.validate_key(key)
            values = [self.validate_value(i) for i in values]
            out[key] = values
        return self.validate(out)

    def to_representation(self, querydict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Inflect a validated query dictionary to a query string."""
        out: Dict[str, List[str]] = {}
        for key, value in querydict.items():
            new_value = [self.represent_value(v) for v in value]
            out[self.represent_key(key)] = new_value
        out = self.represent(out)
        out_escaped = {}
        for key, value in out.items():
            escaped_key = quote_plus(key)
            escaped_value = [quote_plus(v) for v in value]
            out_escaped[escaped_key] = escaped_value
        return out

    def filter_queryset(self, querydict: dict, queryset: QuerySet) -> QuerySet:
        """Filter the queryset."""
        return queryset

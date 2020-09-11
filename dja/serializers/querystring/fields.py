import re

from dja.registry import ResourceRegistry
from dja.serializers.querystring.base import QueryStringField

PATTERN = re.compile(r"fields\[[^\]*\]")


class Fields(QueryStringField):

    flatten = True

    def match_key(self, key):
        return PATTERN.fullmatch(key) is not None

    def validate_key(self, key):
        key = super().validate_key(key)
        subkey = self.extract_subkey(key)
        try:
            serializer_class = ResourceRegistry.get_serializer_class(subkey)
        except LookupError:
            self.fail("invalid")
        inflected_type = serializer_class.dja_get_inflection(subkey)
        new_key = self.replace_subkey(key, inflected_type)
        return new_key

    def validate(self, querydict):
        querydict = super().validate(querydict)
        out = {}
        for key, value in querydict.items():
            _type = self.extract_subkey(key)
            seriaizer_class = ResourceRegistry.get_serializer_class(_type)
            all_fields = seriaizer_class.dja_get_all_fields()
            inflected_field_names = []
            for field_name in value:
                inflected_field_name = seriaizer_class.dja_get_inflection(field_name)
                if inflected_field_name not in all_fields:
                    self.fail("invalid")
                inflected_field_names.append(inflected_field_name)
            out[key] = inflected_field_names
        return out

    def represent_key(self, key):
        key = super().represent_key(key)
        subkey = self.extract_subkey(key)
        serializer_class = ResourceRegistry.get_serializer_class(subkey)
        inflected_type = serializer_class.dja_get_inflection(subkey)
        new_key = self.replace_subkey(key, inflected_type)
        return new_key

    def represent(self, querydict):
        querydict = super().represent(querydict)
        out = {}
        for key, value in querydict.items():
            _type = self.extract_subkey(key)
            seriaizer_class = ResourceRegistry.get_serializer_class(_type)
            inflected_field_names = []
            for field_name in value:
                inflected_field_name = seriaizer_class.dja_get_inflection(field_name)
                inflected_field_names.append(inflected_field_name)
            out[key] = inflected_field_names
        return out

    def filter_queryset(self, querydict, queryset):
        # deferring these fields seems like a risk/difficult
        #   but feel free to experiment.
        return super().filter_queryset(querydict, queryset)

import re

from django.db.models import Q

from dja.serializers.querystring.base import QueryStringField

PATTERN = re.compile(r"filter\[[^\]*\]")


class Filter(QueryStringField):
    def match_key(self, key):
        return PATTERN.fullmatch(key) is not None

    def validate_key(self, key):
        key = super().validate_key(key)
        subkey = self.extract_subkey(key)
        inflected_path = self.validate_dotted_path(subkey, is_filterable=True)
        return self.replace_subkey(key, inflected_path)

    def represent_key(self, key):
        key = super().represent_key(key)
        subkey = self.extract_subkey(key)
        inflected_path = self.represent_dotted_path(subkey)
        return self.replace_subkey(key, inflected_path)

    def filter_queryset(self, querydict, queryset):
        queryset = super().filter_queryset(querydict, queryset)
        all_q = Q()
        for key, value in querydict.items():
            path = self.extract_subkey(key)
            model_chain = self.get_model_chain(path)
            path_q = Q()
            for v in value:
                path_q |= Q(**{model_chain: v})
            all_q &= path_q
        return queryset.filter(all_q)

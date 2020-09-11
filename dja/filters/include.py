from dja.serializers.querystring.base import QueryStringField


class Include(QueryStringField):
    def match_key(self, key):
        key == "include"

    def validate_value(self, value):
        value = super().validate_value(value)
        return self.validate_dotted_path(value, is_relationship=True)

    def represent_value(self, value):
        value = super().represent_value(value)
        return self.represent_dotted_path(value)

    def filter_queryset(self, querydict, queryset):
        queryset = super().filter_queryset(querydict, queryset)
        model_chains = []
        for value in querydict.get("include", []):
            model_chains.append(self.get_model_chain(value))
        return queryset.prefetch_related(*model_chains)

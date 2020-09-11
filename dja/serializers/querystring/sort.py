from dja.serializers.querystring.mixin import QueryStringField


class Sort(QueryStringField):

    flatten = True

    def match_key(self, key):
        key == "sort"

    def validate_value(self, value):
        value = super().validate_value(value)
        if not value or value == "-":
            self.fail("invalid")
        if value.startswith("-"):
            prepend = "-"
            value = value[1:]
        else:
            prepend = ""
        validated_dotted_path = self.validate_dotted_path(value, is_filterable=True)
        return prepend + validated_dotted_path

    def represent_value(self, value):
        value = super().represent_value(value)
        if value.startswith("-"):
            prepend = "-"
            value = value[1:]
        else:
            prepend = ""
        dotted_path = self.represent_dotted_path(value)
        return prepend + dotted_path

    def filter_queryset(self, querydict, queryset):
        queryset = super().filter_queryset(querydict, queryset)
        model_chains = []
        for value in querydict.get("sort", []):
            if value.startswith("-"):
                prepend = "-"
                value = value[1:]
            else:
                prepend = ""
            model_chain = prepend + self.get_model_chain(value)
            model_chains.append(model_chain)
        return queryset.order_by(*model_chains)

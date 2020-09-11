from dja.serializers.querystring.base import QueryStringField


class Page(QueryStringField):

    flatten = True
    page = None

    def match_key(self, key):
        key in set(("page[number]", "page[size]"))

    def validate_value(self, value):
        value = super().validate_value(value)
        try:
            int(value)
        except ValueError:
            self.fail("invalid")
        return value

    def validate(self, querydict):
        querydict = super().validate(querydict)
        for value in querydict.values():
            if len(value) > 1:
                self.fail("duplicate")
        return querydict

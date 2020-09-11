from typing import Union

from rest_framework import fields, relations


class ManyRelatedResourceField(fields.ListField):
    pass


class RelatedResourceField(fields.Field):
    def __new__(cls, *args, **kwargs):
        if kwargs.pop("many", False):
            list_kwargs = {}
            for key in ["child", "allow_empty", "min_length", "max_length"]:
                if key in kwargs:
                    list_kwargs[key] = kwargs.pop(key)
            list_kwargs["child"] = cls(*args, **kwargs)
            return ManyRelatedResourceField(**list_kwargs)
        return super().__new__(cls, *args, **kwargs)

    def use_pk_only_optimization(self):
        return False


def patchpkonly(
    field: Union[RelatedResourceField, ManyRelatedResourceField, relations.RelatedField, relations.ManyRelatedField],
    nopkonly: bool,
):
    """Applies a no-good, dirty patch to related fields.

    I can't think of a safer way to force a `rest_framework.RelatedField` instance
    to have `use_pk_only_optimization == False`. We could try to replicate `get_attribute`,
    but what if this function is modified later?

    Args:
        field: The related field to patch.
        nopkonly: Set to `True` if the field must not return a `PKOnlyObject`.

    Yields: The related field instance which may have been patched according to `nopkonly`.
    """
    try:
        if nopkonly:
            # do our no-good, dirty patch
            if isinstance(field, relations.ManyRelatedField):
                oldfunc = field.child_relation.use_pk_only_optimization
                field.child_relation.use_pk_only_optimization = lambda field: False
            elif isinstance(field, ManyRelatedResourceField):
                oldfunc = field.use_pk_only_optimization
                field.child.use_pk_only_optimization = lambda field: False
            elif isinstance(field, (relations.RelatedField, RelatedResourceField)):
                oldfunc = field.use_pk_only_optimization
                field.use_pk_only_optimization = lambda field: False  # type: ignore

        yield field

    finally:
        if nopkonly:
            # undo our no-good, dirty patch
            if isinstance(field, relations.ManyRelatedField):
                field.child_relation.use_pk_only_optimization = oldfunc
            elif isinstance(field, ManyRelatedResourceField):
                field.child.use_pk_only_optimization = oldfunc
            elif isinstance(field, (relations.RelatedField, RelatedResourceField)):
                field.use_pk_only_optimization = oldfunc  # type: ignore

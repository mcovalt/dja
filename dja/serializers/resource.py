import itertools as it
from collections import ChainMap
from contextlib import suppress
from typing import Any, Dict, Generator, Optional, Type, TypedDict

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.urls.exceptions import NoReverseMatch
from rest_framework import serializers, viewsets
from rest_framework.fields import SkipField
from rest_framework.relations import ManyRelatedField, PKOnlyObject, RelatedField
from rest_framework.utils.model_meta import FieldInfo, get_field_info

import inflect

from dja.pagination import BasePaginator
from dja.registry import ResourceRegistry
from dja.relations import ManyRelatedResourceField, RelatedResourceField, patchpkonly


class ResourceLinks(TypedDict):
    self: str


class RelatedResourceLinks(TypedDict, total=False):
    self: str
    related: str


class QueryPageInnerData(TypedDict):
    number: int
    size: int


class QueryPageData(TypedDict):
    page: QueryPageInnerData


class TopLevelLinks(TypedDict, total=False):
    first: Optional[str]
    previous: Optional[str]
    self: Optional[str]
    next: Optional[str]
    last: Optional[str]


class JsonApiObject(TypedDict, total=False):
    version: str
    meta: dict


class Meta:
    model: Type[models.Model]
    type: str


class ResourceSerializerMixin:
    # DRF interface
    # we try to keep the interface properly duck-typed.
    #   I'm sure there are issues though.
    # class
    Meta: Type[Meta]
    # instance
    initial_data: dict
    fields: dict
    context: dict
    instance: Any
    data: dict

    # DJA variables
    # instance
    dja_query_parameters: dict

    @classmethod
    def dja_get_type(cls) -> str:
        """Gets the resource `type` for this serializer class.

        This will try the following in this order:
        1. get the type from the `ResourceRegistry`
        2. get the type from `cls.Meta.type`
        3. assume the type from `cls.Meta.model`
        """
        with suppress(LookupError):
            return ResourceRegistry.get_type(cls)
        with suppress(AttributeError):
            return cls.Meta.type
        with suppress(AttributeError):
            return cls.dja_get_inflection(cls.Meta.model.__name__)
        raise NotImplementedError("Must define JSON:API `type`.")

    @classmethod
    def dja_get_plural(cls, string: str) -> str:
        """Makes a string plural."""
        return inflect.pluralize(string)

    @classmethod
    def dja_get_inflection(cls, string: str) -> str:
        """Inflects a string to/from the JSON:API representation and internal representation.

        This method makes a camelCase string snake_case and vice versa.
        """
        if "_" in string:
            return inflect.camelize(string, uppercase_first_letter=False)
        return inflect.underscore(string)

    @classmethod
    def dja_get_first_page_link(cls, paginator: BasePaginator) -> Optional[str]:
        """Get the first page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_first_link()
        return None

    @classmethod
    def dja_get_previous_page_link(cls, paginator: BasePaginator) -> Optional[str]:
        """Get the previous page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_previous_link()
        return None

    @classmethod
    def dja_get_self_page_link(cls, paginator: BasePaginator) -> Optional[str]:
        """Get the current page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_self_link()
        return None

    @classmethod
    def dja_get_next_page_link(cls, paginator: BasePaginator) -> Optional[str]:
        """Get the next page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_next_link()
        return None

    @classmethod
    def dja_get_last_page_link(cls, paginator: BasePaginator) -> Optional[str]:
        """Get the last page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_last_link()
        return None

    @classmethod
    def dja_get_page_links(cls, paginator: BasePaginator) -> Optional[TopLevelLinks]:
        """Get the last page link.

        This is called by `ManyResourceSerializer`. If you want more
        advanced control, you may be interested in overriding that method
        since it will give access to the instance.
        """
        with suppress(AttributeError):
            return paginator.get_last_link()
        return None

    @classmethod
    def dja_is_filterable(cls, field_name: str) -> bool:
        """Determine whether a field is filterable.

        This is `True` if the field is indexed.
        """
        fields = cls.dja_get_all_fields()
        try:
            model = cls.Meta.model
            field = fields[field_name]
        except (AttributeError, KeyError, FieldDoesNotExist):
            return False
        modelinfo = cls.dja_get_model_field_info()
        if modelinfo is None:
            return False
        if isinstance(field.source, str):
            sources = field.source.split(".")
        else:
            return False
        for source in sources[:-1]:
            try:
                relationinfo = modelinfo.relations[source]
                model = relationinfo.related_model
                serializer = ResourceRegistry.get_serializer_class(model)
                model = serializer.Meta.model
            except (LookupError, AttributeError):
                return False
            modelinfo = serializer.dja_get_model_field_info()
            if modelinfo is None:
                return False
        with suppress(KeyError, AttributeError):
            return modelinfo.fields[sources[-1]].db_index  # type: ignore
        return False

    @classmethod
    def dja_is_empty_topelevel_link_null(cls, link_name: str) -> bool:
        """Determines whether to include members of the top-level `links` object that are `None`.

        Defaults to `False`.

        Args:
            link_name: The member of the top-level `links` object.
        """
        return False

    @classmethod
    def dja_get_toplevel_jsonapi_meta(cls) -> Optional[dict]:
        """Gets the `meta` member of the top-level `jsonapi` object."""
        return None

    @classmethod
    def dja_get_toplevel_jsonapi(cls) -> Optional[JsonApiObject]:
        """Gets the top-level `jsonapi` object.

        Defaults to the dictionary::
            {
                "version": "1.0"
            }
        """
        jsonapi: JsonApiObject = {}
        jsonapi["version"] = "1.0"
        meta = cls.dja_get_toplevel_jsonapi_meta()
        if meta is not None:
            jsonapi["meta"] = meta
        return jsonapi

    @classmethod
    def dja_get_toplevel_meta(cls) -> Optional[dict]:
        """Gets the top-level `meta` object."""
        return None

    @classmethod
    def dja_get_toplevel_errors(cls) -> Optional[dict]:
        """Gets the top-level `errors` object."""
        # TODO
        return None

    @classmethod
    def dja_is_relationship(cls, field_name: str) -> bool:
        """Determines if the field is a related field.

        This will simply see if the field is a subclass of `rest_framework.relations.RelatedField`
        or `dja.relations.ResourceRelatedField` (or their "many" equivalent). The
        `ResourceRelatedField` allows custom relationships that have different mechanics
        than model based relationships seen in `RelatedField`.

        Args:
            field_name: The name for the field to lookup.
        """
        with suppress(KeyError):
            fields = cls.dja_get_all_fields()
            field = fields[field_name]
            return isinstance(field, (RelatedField, RelatedResourceField, ManyRelatedField, ManyRelatedResourceField))
        return False

    @classmethod
    def dja_is_relationship_many(cls, field_name: str) -> bool:
        """Determines if the related field is a "many=True" kind-of field.

        Args:
            field_name: The name for the related field to lookup.
        """
        with suppress(KeyError):
            fields = cls.dja_get_all_fields()
            field = fields[field_name]
            return isinstance(field, (ManyRelatedField, ManyRelatedResourceField))
        return False

    @classmethod
    def dja_is_attribute(cls, field_name: str) -> bool:
        """Determines if the field is an attribute field.

        Args:
            field_name: The name for the field to lookup.
        """
        return (
            field_name in cls.dja_get_all_fields()
            and field_name not in ("id", "type")
            and not cls.dja_is_relationship(field_name)
        )

    @classmethod
    def dja_pop_excluded_field(cls, field_name: str) -> bool:
        """Determines whether to pop the field from the serializer instance.

        If this is `True`, then the field will be removed from the `fields` dictionary
        and not validated.

        Otherwise, the field will be included and validated, just not sent in the response.

        Args:
            field_name: The name for the excluded field.
        """
        return True

    @classmethod
    def dja_get_relationship_serializer_class(
        cls, field_name: str, relationship_instance=None
    ) -> Type["ResourceSerializerMixin"]:
        """Gets the serializer class for a related field.

        In some cases a field may be polymorphic. Therefore, in addition to the related field name,
        the instance of the related field is also always provided.

        If the `relationship_instance` is a `PKOnlyObject` or `None`, the related
        instance type will be attempted to be inferred based on the related field's model (from
        `RelatedField.queryset.model`). This type is used to lookup the serializer class
        from the `ResourceRegistry`.

        Args:
            field_name: The name for the related field.
            relationship_instance: The instance for this field.
        """
        if relationship_instance is None or isinstance(relationship_instance, PKOnlyObject):
            try:
                fields = cls.dja_get_all_fields()
                field = fields[field_name]
                instance_type = field.queryset.model  # type: ignore
            except (KeyError, AttributeError):
                raise LookupError(
                    f"`dja_get_relationship_serializer_class()` not implemented for field `{field_name}`."
                )
        else:
            instance_type = type(relationship_instance)
        return ResourceRegistry.get_serializer_class(instance_type)

    @classmethod
    def dja_get_all_fields(cls) -> Dict[str, serializers.Field]:
        """Get the dictionary of all fields on this serializer.

        The `Serializer` must be able to be initialized without any arguments.
        This allows us to determine the full set of fields available to make query
        string operations from. Ensure that `Serializer` has all `fields` available
        when given an empty initialization argument list.
        """
        try:
            serializer = cls()
        except:  # noqa: E722
            raise NotImplementedError(
                "The `Serializer` must be able to be initialized without any arguments."
                "This allows us to determine the full set of fields available to make query"
                "string operations from. Ensure that `Serializer` has all `fields` available"
                "when given an empty initialization argument list."
            )
        return serializer.fields

    @classmethod
    def dja_get_model_field_info(cls) -> Optional[FieldInfo]:
        with suppress(AttributeError):
            model = cls.Meta.model
            return get_field_info(model)
        return None

    def dja_get_id(self) -> str:
        """Gets the resource object `id` for this serializer.

        You'll need to rewrite this if `id` is manipulated in `to_representation`.
        Many times just the resource identifier is required (i.e. just `type` and
        `id`). In these cases, serializing the whole object can be ineffecient.
        """
        field = self.fields["id"]
        attribute = None
        with suppress(SkipField):
            attribute = field.get_attribute(self.instance)
        if attribute is None:
            raise ValueError("Tried to get the JSON:API `id` from the instance, but the `id` attribute was `None`.")
        representation = field.to_representation(attribute)
        return str(representation)

    def dja_get_meta(self) -> Optional[dict]:
        """Gets the resource `meta` object."""
        return None

    def dja_get_relationship_meta(self, field_name: str) -> Optional[dict]:
        """Gets the related resource `meta` object.

        Args:
            field_name: The name for the related field.
        """
        return None

    def dja_get_viewset(self) -> Optional[viewsets.ViewSet]:
        """Gets the `ViewSet` for this serializer."""
        viewset_class = ResourceRegistry.get_viewset_class(type(self))
        if viewset_class is not None:
            viewset = viewset_class()
            viewset.request = self.context.get("request")
            return viewset
        return None

    def dja_get_self_link(self) -> Optional[str]:
        """Gets the resource object `self` link."""
        viewset = self.dja_get_viewset()
        if viewset is not None:
            with suppress(NoReverseMatch):
                return viewset.reverse_action("detail", args=[self.dja_get_id()])
        return None

    def dja_get_links(self) -> Optional[ResourceLinks]:
        """Gets the resource object `links` member."""
        self_link = self.dja_get_self_link()
        if self_link:
            return {"self": self_link}
        return None

    def dja_get_relationship_self_link(self, field_name: str) -> Optional[str]:
        """Gets the relationship resource `self` link.

        Args:
            field_name: The name for the relationship field.
        """
        viewset = self.dja_get_viewset()
        if viewset is not None:
            with suppress(NoReverseMatch):
                return viewset.reverse_action("relationship-self", args=[self.dja_get_id(), field_name])
        return None

    def dja_get_relationship_related_link(self, field_name: str) -> Optional[str]:
        """Gets the related resource `related` link.

        Args:
            field_name: The name for the related field.
        """
        viewset = self.dja_get_viewset()
        if viewset is not None:
            with suppress(NoReverseMatch):
                return viewset.reverse_action("relationship-related", args=[self.dja_get_id(), field_name])
        return None

    def dja_get_relationship_links(self, field_name: str) -> Optional[RelatedResourceLinks]:
        """Gets the relationship resource `links` member.

        Args:
            field_name: The name for the relationship field.
        """
        self_link = self.dja_get_relationship_self_link(field_name)
        related_link = self.dja_get_relationship_related_link(field_name)
        links: RelatedResourceLinks = {}
        if self_link:
            links["self"] = self_link
        if related_link:
            links["related"] = related_link
        return links or None

    def dja_is_relationship_data_provided(self, field_name: str) -> bool:
        """Whether to provide the relationships data.

        Note you _MUST_ either provide data and/or links.

        Args:
            field_name: The name for the relationship field.
        """
        return True

    def dja_get_relationship_instances(self, field_name: str, nopkonly=False) -> Generator[Any, None, None]:
        """Gets all the related instances for a related field.

        This does not yield `None`.

        Args:
            field_name: The name for the related field.
            nopkonly: Do not allow a `PKOnlyObject` to be returned. Default is `False`.
        """
        with patchpkonly(self.fields[field_name], nopkonly) as field:
            with suppress(SkipField):
                instance = field.get_attribute(self.instance)
                if self.dja_is_relationship_many(field_name):
                    yield from instance
                elif instance is not None:
                    yield instance

    def dja_get_relationship_serializer_kwargs(self, field_name: str) -> dict:
        """Gets the serializer kwargs for a related field.

        Sometimes extra kwargs must be passed to a related serializer if the
        custom `__init__` method is implemented on the related serializer. This
        function allows providing these kwargs. By default, `context` is passed in.

        Args:
            field_name: The name for the related field.
        """
        return {"context": self.context}

    def dja_get_relationship_serializers(
        self, field_name: str, nopkonly=False, **kwargs
    ) -> Generator["ResourceSerializerMixin", None, None]:
        """Gets the serializers for a related field.

        Args:
            field_name: The name for the related field.
            nopkonly: Do not allow a `PKOnlyObject` to be returned. Default is `False`.
            **kwargs: Any additional kwargs to pass to the serializer. These kwargs override
                those provided by `self.dja_get_related_serializer_kwargs(field_name)`
        """
        for instance in self.dja_get_relationship_instances(field_name, nopkonly=nopkonly):
            serializer_class = self.dja_get_relationship_serializer_class(field_name, instance)
            yield serializer_class(  # type: ignore
                instance, **ChainMap(kwargs, self.dja_get_relationship_serializer_kwargs(field_name))
            )

    def dja_get_included_serializers(self):
        """Gets the included serializers.

        Only serializers on the full path to destination included field should be yielded. The
        sequence of yielded serializers are unique.
        """
        # we have to keep track of yielded resources
        #   you could have two field names pointing to the same resource
        #   this is initialized with `self` since it acts as the root of this tree
        yielded_resources = set(((self.dja_get_type(), self.dja_get_id()),))
        # TODO: build tree of field names. we duplicate a lot by iterating
        #   this way. e.g. include string "foo.bar.bat" and "foo.bar.baz"
        #   will traverse "foo.bar" twice.
        for include_string in self.dja_query_parameters["include"]:
            field_names = include_string.split(".")
            # `serializer_path[-1]` is always the serializer responsible for creating `generator_stack[-1]`
            serializer_path = [self]
            generator_stack = [self.dja_get_relationship_serializers(field_names[0], nopkonly=True)]
            while generator_stack:
                try:
                    # get the next serializer
                    generator = generator_stack[-1]
                    serializer = next(generator)
                    serializer_path.append(serializer)
                except StopIteration:
                    # this generator has been exhausted
                    generator_stack.pop()
                    serializer_path.pop()
                    continue
                if len(generator_stack) == len(field_names):
                    # we've reached a leaf node
                    # TODO: we don't need to check the whole serializer path every time
                    for serializer in it.chain(serializer_path, generator):
                        resource_id = (serializer.dja_get_type(), serializer.dja_get_id())
                        if resource_id not in yielded_resources:
                            yield serializer
                            yielded_resources.add(resource_id)
                    # pop the first leaf node from the serializer path
                    serializer_path.pop()
                else:
                    # add to the generator stack
                    field_name = field_names[len(generator_stack) + 1]
                    generator_stack.append(serializer.dja_get_relationship_serializers(field_name, nopkonly=True))

    def _dja_get_attributes(self) -> Dict[str, Any]:
        """Get the `attributes` member of the `data` object.

        This method is private since it deals with inflection.
        """
        attributes = {}
        for field_name in self.data:
            if self.dja_is_attribute(field_name):
                attributes[self.dja_get_inflection(field_name)] = self.data[field_name]
        return attributes

    def _dja_get_relationships(self) -> dict:
        """Get the `relationships` member of the `data` object.

        This method is private since it deals with inflection.
        """
        relationships = {}
        data = []
        for field_name in self.data:
            if self.dja_is_relationship(field_name):
                for serializer in self.dja_get_relationship_serializers(field_name):
                    data.append(
                        {
                            "type": serializer.dja_get_inflection(serializer.dja_get_type()),
                            "id": serializer.dja_get_id(),
                        }
                    )
                relationship: dict = {}
                links = self.dja_get_relationship_links(field_name)
                meta = self.dja_get_relationship_meta(field_name)
                if links:
                    relationship["links"] = links
                if self.dja_is_relationship_many(field_name):
                    relationship["data"] = data
                else:
                    relationship["data"] = data[0] if data else None
                if meta:
                    relationship["meta"] = meta
                relationships[self.dja_get_inflection(field_name)] = relationship
        return relationships

    def _dja_get_data(self) -> dict:
        """Get the `data` member of the resource object.

        This method is private since it deals with inflection.
        """
        data: dict = {}
        data["type"] = self.dja_get_inflection(self.dja_get_type())
        data["id"] = self.dja_get_id()
        attributes = self._dja_get_attributes()
        if attributes:
            data["attributes"] = attributes
        relationships = self._dja_get_relationships()
        if relationships:
            data["relationships"] = relationships
        return data


class ManyResourceSerializerMixin:
    pass

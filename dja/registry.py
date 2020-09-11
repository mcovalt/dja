from typing import Any, Dict, Type, Union

from dja.serializers.resource import ResourceSerializerMixin
from dja.views import ResourceViewSet


class empty:
    pass


class ResourceRegistry:
    viewset_map: Dict[Type[ResourceSerializerMixin], Type[ResourceViewSet]] = {}
    instanceclass_map: Dict[Type[ResourceSerializerMixin], Type[Any]] = {}
    serializerclass_map: Dict[
        Union[Type[ResourceViewSet], Type[Any], Type[ResourceSerializerMixin], str], Type[ResourceSerializerMixin]
    ] = {}
    type_map: Dict[Type[ResourceSerializerMixin], str] = {}

    @classmethod
    def get_viewset_class(cls, serializer_class: Type[ResourceSerializerMixin], default=empty):
        try:
            return cls.viewset_map[serializer_class]
        except KeyError:
            if default is not empty:
                return default
            raise LookupError(f"Could not find ViewSet class for serializer {serializer_class}.")

    @classmethod
    def get_instance_class(cls, serializer_class, default=empty):
        try:
            return cls.instanceclass_map[serializer_class]
        except KeyError:
            if default is not empty:
                return default
            raise LookupError(f"Could not find instance class for serializer {serializer_class}.")

    @classmethod
    def get_type(cls, serializer_class, default=empty):
        try:
            return cls.type_map[serializer_class]
        except KeyError:
            if default is not empty:
                return default
            raise LookupError(f"Could not find JSON:API type for serializer {serializer_class}.")

    @classmethod
    def get_serializer_class(cls, key, default=empty):
        try:
            return cls.serializerclass_map[key]
        except KeyError:
            if default is not empty:
                return default
            if isinstance(key, str):
                raise LookupError(f"Could not find serializer class for JSON:API type '{key}'.")
            raise LookupError(f"Could not find serializer class for '{key}'.")

    @classmethod
    def _register(cls, registry_map, serializer_class, value):
        if value in cls.serializerclass_map:
            duplicate = cls.serializerclass_map.get(value)
            raise ValueError(f"{value} is already registered to {duplicate}")
        if serializer_class in registry_map:
            duplicate = registry_map.get(serializer_class)
            raise ValueError(f"{serializer_class} is already registered to {duplicate}")
        registry_map[serializer_class] = value
        cls.serializerclass_map[value] = serializer_class

    @classmethod
    def register(cls, serializer_class, instance_class=None, type=None, viewset=None):
        if instance_class is not None:
            cls._register(cls.instanceclass_map, serializer_class, instance_class)
        if type is not None:
            cls._register(cls.type_map, serializer_class, type)
            if type != serializer_class.inflect(type):
                cls._register(cls.type_map, serializer_class, serializer_class.inflect(type))
        if viewset is not None:
            cls._register(cls.viewset_map, serializer_class, viewset)

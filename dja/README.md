# dja Design Doc
### Django JSON:API support

## What?

A package to create JSON:API compatible endpoints in Django REST Framework.

The goals of the package:
<ol>
  <li>Completely support the JSON:API spec.</li>
  <ol type="a">
    <li>Behavior supporting MUST, MUST NOT, REQUIRED, SHALL, and SHALL NOT specifications are not intended to be modifiable. Modification of these behaviors may break the application.</li>
    <li>Behavior supporting SHOULD, SHOULD NOT, RECOMMENDED, SHALL, and SHALL NOT specifications will be default behavior. Modifications should be accessible.</li>
    <li>Behavior supporting MAY and OPTIONAL may or may not be default behavior. Modifications should be accessible.</li>
  </ol>
  <li>Interfere with the serializer as little as possible. Instead, functions required to derive additional information required to comply with the JSON:API should be accessible outside the serializer instance.</li>
  <li>Able to wire up a compatible serializer to correct views with minimal effort.</li>
  <li>Provide utilities to facilitate the creation of all aspects of the JSON:API spec.</li>
  <li>Work with built-in Django REST Framework tooling to provide automatic generation of the OpenAPI schema.</li>
</ol>

## Why?

Another package exists for this purpose, [django-rest-framework-json-api](https://github.com/django-json-api/django-rest-framework-json-api). It fails to comply with Django REST Framework due to [an issue](https://github.com/django-json-api/django-rest-framework-json-api/issues/155) where the resource identifier cannot be custom. Also, the following bugs/oddities have been identified and fickle code has been implemented to address them:
- Polymorphic serializers return the incorrect `self` link.
- Polymorphic serializers do not allow `__init__` kwargs to be passed into the child serializers.
- Related types are not consistently inflected.
- Query parameters are not customizable.
- Validation, inflection, and logic is spread across custom parsers, custom renderers, custom serializers, custom related fields, and custom views. This makes addressing bugs very difficult.

Advancements in the way Django REST Framework serializers work allow all of this logic to be placed in the serializer which would allow significantly less code and more consistent access points for customization.

## How?

A `ResourceSerializerMixin` will add the following functions to any serializer instance.
- `get_related_self_link(self, field_name)`, `get_related_link(self, field_name)`, `get_self_link(self)`: Default will return a link if the view is found. Return `None` if not found. A return of `None` will not display a link.
- `get_related_meta(self, field_name)`, `get_meta(self)`: Return metadata for the relationship object and the resource object. A return of `None` will not add meta information. Default returns `None`.
- `get_related_serializer(cls, field_name)`: Default implementation will find serializer in registry associated with model instance. Return `None` if not found. A return of `None` will render the field as an attribute. Must be a class method for relationship view.
- `is_type_valid(cls, type, instance=None)`: Determine if the type provided is valid. Optionally, refer to an instance of the resource (e.g. for polymorphic serializers). Must be a class method for validation of type in related serializers.
- `inflect(cls, field_name)`: Default implementation will snake_case -> camelCase member names and type. Must be a class method for inflection before the the serializer is instantiated.
- `deflect(cls, field_name)`: Default implementation will camelCase -> snake_case member names and type. Must be a class method for inflection before the the serializer is instantiated.
- `__init_subclass__(self, *args, **kwargs)`: Adds the serializer to a registry associating its model with the serializer class (if possible).

A mixin allows the serializer to behave normally outside the context of a tool that makes use of this information (described below). It doesn't restrict the serializer's base which allows for thirdparty serializer bases to be used. Although default behavior is established for the most common case of a ModelSerializer, unsupported serializers (or modifications of the default behavior) are easily supported via implementing or overriding the above functions. No methods will be modified that are included in the default serializer class. This prevents unexpected behavior for when a developer modifies these functions (e.g. `to_representation`). Any serializer mixed with this mixin will here on be referred to as a `ResourceSerializer`. A dummy `RelatedResourceField` will act as a base serializer for custom relationships.

A `JSONAPISerializer` will construct the JSON:API response. It is initialized with the `ResourceSerializer`, and args and kwargs meant for the `ResourceSerializer`. It inherits `rest_framework.serializers.BaseSerializer`. It implements the following functions:
- `to_representation(self, instance)`: Forms the JSON:API response. Processes `include` and `fields` query parameters. Inflects/transforms member names and types.
- `to_internal_value(self, data)`: Processes the JSON:API request.
- `run_validation(self, data=empty)` Runs validation on `ResourceSerializer`. Additionally, validates type and related types. Coerces `ValidationError` objects from the `ResourceSerializer` into an exception that complies with JSON:API.

Note: The typical behavior of `many=True` should be implemented differently in this serializer. It will be handled explicitly in `to_representation(self, instance)` and `to_internal_value(self, data)`. A `ListSerializer` is great for fields, but unnessesary for the child serializer. It would be nice to add our custom behavior to the via `many_init` on the `ResourceSerializer`, but this adds a layer to the `ResourceSerializer` that has unexpected consequences when modified which is avoided. Perhaps customization can be established in a class method on the `ResourceSerializerMixin` later.

The `JSONAPISerializer` is not usually handled by the user, but instead instantiated with the provided `ResourceSerializer` in a `ViewSet`.

A `ResourceViewSetMixin` will implement the routes for the `JSONAPISerializer`. It adds the following to a view:
- `filter_queryset(self, queryset)`: Filters the queryset according to query parameters.
- `get_querysring_serializer_class(self)`: Gets the serializer to process the querysring (described below).
- `get_querysring_serializer(self, querystring)`: Return the instantiated querystring serializer. Raises validation errors if seen.
- `get_serializer_context(self)`: Add the querystring serializer to the context.
- `paginate_queryset(self, queryset)`: Uses the querystring serializer to determine pagination.
- `list(self, request, *args, **kwargs)`, `retrieve(self, request, *args, **kwargs)`, `partial_update(self, request, *args, **kwargs)`, `delete(self, request, *args, **kwargs)`: Implement JSON:API spec for GET, POST, PATCH, and DELETE.
- Actions for `*_related(self, request, *args, **kwargs)`, `retrieve_relationships(self, request, *args, **kwargs)` where `*` indicates actions for GET, POST, PATCH: Implement JSON:API spec for relationships.
- `get_serializer(self, instance=None, data=None, many=False, partial=False)`: Instantiates the `JSONAPISerializer` with the `ResourceSerializer`.
- `ResourceAutoSchema`: generates the OpenAPI schema.

A `QueryStringSerializer` will implement the serialization of JSON:API querystrings. It will have the following:
- The `fields`, `include`, `sort`, `filter`, and `page` fields.
- `to_internal_value(self, data)`: Builds a dictionary from the querystring.
- `to_representation(self, instance)`: Builds a querystring from the serializer data.

A `ResourceException` may be implemented to provide a `rest_framework.exceptions.ValidationError` like object with additional support for the extra information JSON:API allows for errors. It may be possible to just use `rest_framework.exceptions.ValidationError` by instantiating it with a `dict`.

A `ResourceRouter` will register the `ResourceViewSet` URLs and associate the `ViewSet` with the serializer. A `register_model(cls, serializer, model)` and a `register_view(cls, serializer, view)` are classmethods on the `ResourceRegistry` to be used to build the registry for custom applications. These registries are needed to resolve links and related types.

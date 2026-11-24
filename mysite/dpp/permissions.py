"""Ownership rules for data that belongs to a user.

A ProductionLine belongs to the user who created it. Processes,
transport entries, publishers and the exchanges of a process belong to
the owner of their production line.

A product (Flow) belongs to the owner of the production line that makes
it: as the output of a Process, or as the final product of the line.
Data attached to a product (properties, DPP details, composition,
evaluations and their scores, ...) belongs to the owner of that
product. A product that no production line makes is shared.

A published DPP (Metadata) belongs to the owner of its product batch.
If no production line makes the batch (publishing a product model
creates a new batch), the DPP belongs to the owner of the product model.
The public DPP page and the API show every DPP (see api.views).

Everything else (companies, materials, background processes, ...) is
shared reference data that every logged-in user can use.

Staff users can see and edit everything.
"""
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db.models import Q

from .models import (
    Activity, EnvExchange, Flow, Metadata, Process, ProductExchange,
    ProductionLine, ProductItem, Publisher, Transport,
)

# Lookup path from a Metadata (DPP) to its product batch
DPP_BATCH = "product_item__product_batch__"


def is_privileged(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


def _flow_owner(flow):
    """Return the owner of the production line that makes `flow`, or None."""
    try:
        return flow.produced_by.production_line.created_by
    except ObjectDoesNotExist:
        pass
    try:
        return flow.productionline.created_by
    except ObjectDoesNotExist:
        return None


def _unowned_q(prefix=""):
    """Q filter for the flows (at `prefix`) that no production line makes."""
    return Q(**{f"{prefix}produced_by__isnull": True}) & Q(
        **{f"{prefix}productionline__isnull": True}
    )


def _owned_by_q(user, prefix=""):
    """Q filter for the flows (at `prefix`) that a line of `user` makes."""
    return Q(**{f"{prefix}produced_by__production_line__created_by": user}) | Q(
        **{f"{prefix}productionline__created_by": user}
    )


def _flow_q(user, prefix=""):
    """Q filter for the flows (at `prefix`) that `user` may see."""
    return _unowned_q(prefix) | _owned_by_q(user, prefix)


def _dpp_q(user):
    """Q filter for the DPPs (Metadata) that `user` may see."""
    batch, model = DPP_BATCH, f"{DPP_BATCH}model__"
    return (
        _owned_by_q(user, batch)
        | (_unowned_q(batch) & (_unowned_q(model) | _owned_by_q(user, model)))
    )


def _product_path(model):
    """Return the lookup path from `model` to the Flow it describes, or None.

    Examples: "product" (ProductProperties), "product_batch" (ProductItem),
    "evaluation__product" (SustainabilityScore, CircularityScore).
    """
    if issubclass(model, ProductItem):
        return "product_batch"
    try:
        field = model._meta.get_field("product")
        if field.is_relation and issubclass(field.related_model, Flow):
            return "product"
    except FieldDoesNotExist:
        pass
    try:  # Scores belong to an evaluation of a product
        field = model._meta.get_field("evaluation")
    except FieldDoesNotExist:
        return None
    if field.is_relation and (path := _product_path(field.related_model)):
        return f"evaluation__{path}"
    return None


def get_owner(obj):
    """Return the user who owns `obj`, or None for shared data."""
    if isinstance(obj, ProductionLine):
        return obj.created_by
    if isinstance(obj, (Process, Transport, Publisher)):
        return obj.production_line.created_by
    if isinstance(obj, (ProductExchange, EnvExchange)):
        return get_owner(obj.process)
    if isinstance(obj, Activity):
        try:  # An Activity may be the parent row of a Process
            return obj.process.production_line.created_by
        except ObjectDoesNotExist:
            return None
    if isinstance(obj, Flow):
        return _flow_owner(obj)
    if isinstance(obj, Metadata):
        batch = obj.product_item.product_batch
        return _flow_owner(batch) or _flow_owner(batch.model)
    if path := _product_path(type(obj)):
        product = obj
        for name in path.split("__"):
            product = getattr(product, name, None)
        return _flow_owner(product) if product else None
    return None


def can_access(user, obj) -> bool:
    """True if `user` may view or change `obj`."""
    if is_privileged(user):
        return True
    owner = get_owner(obj)
    return owner is None or owner == user


def filter_owned(queryset, user):
    """Limit `queryset` to objects that `user` may see."""
    if is_privileged(user):
        return queryset
    if not (user and user.is_authenticated):
        return queryset.none()
    model = queryset.model
    if issubclass(model, ProductionLine):
        return queryset.filter(created_by=user)
    if issubclass(model, (Process, Transport, Publisher)):
        return queryset.filter(production_line__created_by=user)
    if issubclass(model, (ProductExchange, EnvExchange)):
        return queryset.filter(
            Q(process__process__isnull=True)
            | Q(process__process__production_line__created_by=user)
        )
    if model is Activity:
        return queryset.filter(
            Q(process__isnull=True)
            | Q(process__production_line__created_by=user)
        )
    if issubclass(model, Flow):
        return queryset.filter(_flow_q(user))
    if issubclass(model, Metadata):
        return queryset.filter(_dpp_q(user))
    if path := _product_path(model):
        return queryset.filter(_flow_q(user, f"{path}__"))
    return queryset


def limit_form_choices(form, user):
    """Hide other users' production lines and processes in form dropdowns."""
    for field in form.fields.values():
        queryset = getattr(field, "queryset", None)
        if queryset is not None:
            field.queryset = filter_owned(queryset, user)
    return form

"""Ownership rules for data that belongs to a user.

A ProductionLine belongs to the user who created it. Processes,
transport entries, publishers and the exchanges of a process belong to
the owner of their production line. Everything else (companies,
materials, products, background processes, ...) is shared reference
data that every logged-in user can use.

Staff users can see and edit everything.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from .models import (
    Activity, EnvExchange, Process, ProductExchange, ProductionLine,
    Publisher, Transport,
)


def is_privileged(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


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
    return queryset


def limit_form_choices(form, user):
    """Hide other users' production lines and processes in form dropdowns."""
    for field in form.fields.values():
        queryset = getattr(field, "queryset", None)
        if queryset is not None:
            field.queryset = filter_owned(queryset, user)
    return form

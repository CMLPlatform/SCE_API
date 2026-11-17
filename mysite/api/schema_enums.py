"""Choice sets for drf-spectacular ENUM_NAME_OVERRIDES.

The settings refer to these functions by import path. drf-spectacular
calls them after the apps load, so the model imports here are safe.
"""
from django_countries import countries


def country_choices():
    return list(countries)


def _field_choices(model, field):
    return model._meta.get_field(field).choices


def mass_unit_choices():
    from dpp.models import ProductProperties
    return _field_choices(ProductProperties, 'weight_unit')


def volume_unit_choices():
    from dpp.models import ProductProperties
    return _field_choices(ProductProperties, 'volume_unit')


def life_cycle_event_type_choices():
    from dpp.models import LifeCycleEvent
    return _field_choices(LifeCycleEvent, 'type')

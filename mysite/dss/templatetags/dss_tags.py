from django import template

register = template.Library()

@register.filter
def get_field(form, field_name: str):
    """{{ form|get_field:"group_weight_economic" }} → the BoundField."""
    return form[field_name]

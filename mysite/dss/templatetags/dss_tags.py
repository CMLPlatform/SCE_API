from django import template

register = template.Library()

@register.filter
def get_field(form, field_name: str):
    """{{ form|get_field:"group_weight_economic" }} → the BoundField."""
    return form[field_name]
 
@register.filter
def get_item(dict, key):
    """Get value from dict: dict[key]."""
    return dict.get(key, [])

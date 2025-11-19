from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr):
    """Get attribute from object"""
    return getattr(obj, attr, '')

@register.filter
def get_fields(obj):
    """Get all fields from a model instance"""
    fields = []
    for field in obj._meta.fields:
        fields.append({
            'name': field.name,
            'value': get_attr(obj, field.name)
        })
    return fields

@register.filter
def get_verbose_fields(obj):
    """Get the verbose fields (for printing) from a model instance"""
    fields = []
    for field in obj._meta.fields:
        if field not in ['id']:
            name = field.verbose_name if field.verbose_name else field.name
            fields.append({
                'name': name,
                'value': getattr(obj, field.name, '—')
            })
    return fields
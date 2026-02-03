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
            'verbose_name': field.verbose_name,
            'value': get_attr(obj, field.name)
        })
    try:  # Try to add related properties fields
        for field in obj.properties._meta.fields:
            if not field.name.endswith('_ptr'):
                fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name,
                    'value': get_attr(obj, field.name)
                })
    except:
        pass
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

@register.filter
def sentencecase(obj: str):
    if len(obj) == 1:
        return obj.upper()
    else:
        return obj[0].upper() + obj[1:]

@register.filter
def lookup(dictionary, key):
    return dictionary.get(key)

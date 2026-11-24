from django import forms
from django.urls import reverse, reverse_lazy
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.contrib import admin

class CustomRFWidget(RelatedFieldWidgetWrapper):
    def get_related_url(self, info, action, *args):
        return reverse_lazy("%s:%s_%s" % (info + (action,)))

def get_model_form_plus(thismodel):
    class FormWithAutoAdd(forms.ModelForm):
        """
        A ModelForm mixin that automatically adds a "+" (add another) button
        next to every ForeignKey field, fully compatible with Crispy forms
        """
        class Meta:
            model = thismodel
            exclude = ['created_by']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            for field_name, field in self.fields.items():
                # Detect ForeignKey fields (ModelChoiceField with queryset)
                if isinstance(field, forms.ModelChoiceField) and field.queryset.model:
                    # Get the default widget for the M2M field
                    self.fields[field_name].widget = CustomRFWidget(
                        widget=self.fields[field_name].widget,
                        rel=thismodel._meta.get_field(field_name).remote_field,
                        admin_site=admin.site,  # reuse admin URLs and permissions
                        can_add_related=True,
                        can_change_related=False,  # add edit pencil (only works if action change -> update)
                        can_delete_related=False,
                        can_view_related=False,
                    )
            if is_background:
                self.databases = _installed_databases()
                current = self.instance.database
                choices = [('', '---------')] + [(db, db) for db in self.databases]
                if current and current not in self.databases:
                    choices.append((current, f"{current} (not installed)"))
                self.fields['database'].widget = forms.Select(choices=choices)
                self.fields['database'].help_text = "The LCA database that holds this process."
                self.fields['db_code'].help_text = (
                    "The code of the activity in that database. Required when you choose a database.")

        def clean(self):
            cleaned = super().clean()
            if is_background:
                _clean_background_link(self, cleaned)
            return cleaned

    from .models import BackgroundProcess
    is_background = issubclass(thismodel, BackgroundProcess)
    return FormWithAutoAdd


def _installed_databases():
    """Installed LCA databases, or [] when Brightway is not set up."""
    from . import lca
    try:
        return lca.installed_databases()
    except Exception:
        return []


def _clean_background_link(form, cleaned):
    """Check that a background process links to an activity that exists.

    When the code is empty or unknown, the error suggests matching activities.
    """
    from . import lca
    database, code = cleaned.get('database'), cleaned.get('db_code', '').strip()
    if not database or database not in form.databases:
        return  # No link, or a database that is not installed: step 5 reports it
    if code:
        try:
            lca.bwd.get_activity((database, code))
            return
        except Exception:
            problem = f"The code '{code}' is not in '{database}'."
    else:
        problem = f"Enter the code of the activity in '{database}'."
    flow = cleaned.get('functional_flow')
    search = str(flow.model.name if flow and hasattr(flow, 'model') else cleaned.get('name', ''))
    matches = []
    for text in dict.fromkeys([search, search.split(',')[0].strip()]):  # full name, then the first part
        try:
            matches = lca.find_activities(database, text) if text else []
        except Exception:
            matches = []
        if matches:
            search = text
            break
    if matches:
        problem += (f" Click the field to choose an activity "
                    f"that matches '{search}', or type a code.")
        # Offer the matches as suggestions, so the user does not copy codes by hand
        form.fields['db_code'].widget = SuggestionInput(choices=[
            (m['code'], f"{m['name']} ({m['location']}, {m['unit']})") for m in matches])
    form.add_error('db_code', problem)


class SuggestionInput(forms.TextInput):
    """A text input with a list of suggested values (an HTML <datalist>)."""
    def __init__(self, choices, attrs=None):
        super().__init__(attrs)
        self.choices = choices

    def render(self, name, value, attrs=None, renderer=None):
        from django.utils.html import format_html, format_html_join
        list_id = f"{(attrs or {}).get('id', 'id_' + name)}_suggestions"
        attrs = {**(attrs or {}), 'list': list_id, 'autocomplete': 'off'}
        options = format_html_join('', '<option value="{}">{}</option>', self.choices)
        return format_html('{}<datalist id="{}">{}</datalist>',
                           super().render(name, value, attrs, renderer), list_id, options)
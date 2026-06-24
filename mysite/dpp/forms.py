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
    
    return FormWithAutoAdd
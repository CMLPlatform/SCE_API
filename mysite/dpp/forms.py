from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML
from django.urls import reverse_lazy
# from django.db import models

def get_model_form_plus(thismodel, used_fields):

    class FormWithAutoAdd(forms.ModelForm):
        """
        A ModelForm mixin that automatically adds a "+" (add another) button
        next to every ForeignKey field, fully compatible with Crispy forms
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.helper = FormHelper()
            self.helper.form_tag = False  # We handle <form> in template
            self.helper.disable_csrf = True  # We'll add {% csrf_token %} manually

            layout_fields = []

            for field_name, field in self.fields.items():
                # Detect ForeignKey fields (ModelChoiceField with queryset)
                if isinstance(field, forms.ModelChoiceField) and field.queryset.model:
                    related_model = field.queryset.model
                    model_name = related_model._meta.model_name.lower()

                    add_url = reverse_lazy(f"dpp:{model_name}_add")

                    plus_button = HTML(f'''
                        <a href="{add_url}?_to_field=id&_popup=1"
                        class="related-widget-wrapper-link add-related inline-block ml-2"
                        id="add_id_{field_name}"
                        title="Add another {related_model._meta.verbose_name}"
                        onclick="return showAddAnotherPopup(this);">
                            <svg class="w-5 h-5 text-green-600 hover:text-green-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                            </svg>
                        </a>
                    ''')

                    # Wrap field + button in a flex div for nice alignment
                    layout_fields.append(
                        Field(
                            field_name,
                            wrapper_class="flex items-center gap-3 mb-4"
                        )
                    )
                    layout_fields.append(plus_button)
                else:
                    layout_fields.append(field_name)

            self.helper.layout = Layout(*layout_fields)

        class Meta:
            model = thismodel
            fields = used_fields
    
    return FormWithAutoAdd
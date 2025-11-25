from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from .models import ProductionLine
from api.serializers import ProductionLineSerializer

def home(request):
    
    latest_lines = ProductionLine.objects.order_by("-modified_at")[:5]
    if len(latest_lines) > 5:
        latest_lines = latest_lines[:5]
    context = {'latest_lines': latest_lines}
    return render(request, "dpp/index.html", context)

    # output = ", ".join([pl.name for pl in latest_lines])
    # return HttpResponse(
    #     "Welcome to the Lasers4MaaS project.\n" 
    #     "Last modified production lines: %s" % output
    # )


# Manual views for the production line
def production_line_create(request):
    if request.method == "POST":
        serializer = ProductionLineSerializer(data=request.POST)
        if serializer.is_valid():
            production_line = serializer.save()
            messages.success(request, "Production line created successfully!")
            return redirect("factory:production_line_edit", pk=production_line.pk)
        else:
            # HTMX will re-render the form with errors
            return render(request, "factory/production_line_form.html", {
                "form_data": request.POST,
                "errors": serializer.errors,
            })

    return render(request, "factory/production_line_form.html")

def production_line_edit(request, pk):
    line = ProductionLine.objects.get(pk=pk)
    return render(request, "production_line_edit.html", {"line": line})

class ProductionLineDetailView(DetailView):
    model = ProductionLine
    template_name = 'production_line_detail.html'
    # context_object_name = 'production_line'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add associated processes to the context
        context['processes'] = Process.objects.filter(
            production_line=self.object
        ).order_by('id')
        return context

# Views based on the admin templates
from django.utils.safestring import mark_safe
from django.db.models import ForeignKey
from django.forms import widgets
from django.conf import settings
from django.urls import reverse, reverse_lazy
from .models import (
    Institution, Company, Importer, ServiceOperator, Metadata, Document,
    Material, HazardousMaterial, CriticalRawMaterial, ProductType,
    Packaging, SecondaryProduct, Emission, Composition, Product,
    ProductionLine, Process, SharedProcess, Exchange,
    ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo,
    ServiceEvent, ServiceRecord, ReplacedComponents, EndOfLife,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, OldCircularityIndicator, CircularityIndicator,
    CircularityScore, CircularityEnabler,
)


class RelatedFieldWidgetCanAdd(widgets.Select):
    """Widget consisting of a '+' icon and a link to popup a 'create' form.
    """
    # Source - https://stackoverflow.com/questions/28068168/django-adding-an-add-new-button-for-a-foreignkey-in-a-modelform
    # Retrieved 2025-11-21, License - CC BY-SA 4.0

    def __init__(self, related_model, related_url=None, *args, **kwargs):

        super(RelatedFieldWidgetCanAdd, self).__init__(*args, **kwargs)

        if not related_url:
            info = (related_model._meta.app_label, related_model._meta.object_name.lower())
            related_url = 'admin:%s_%s_add' % info

        # Be careful that here "reverse" is not allowed
        self.related_url = related_url

    def render(self, name, value, *args, **kwargs):
        self.related_url = reverse(self.related_url)
        output = [super(RelatedFieldWidgetCanAdd, self).render(name, value, *args, **kwargs)]
        output.append('<a href="%s?_to_field=id&_popup=1" class="add-another" id="add_id_%s" onclick="return showAddAnotherPopup(this);"> ' % (self.related_url, name))
        output.append('<img src="%sadmin/img/icon_addlink.gif" width="10" height="10" alt="%s"/></a>' % (settings.STATIC_URL, 'Add another'))
        return mark_safe(''.join(output))

def customize_form(db_field, **kwargs):
    """Customize some form fields by adding a widget"""
    if isinstance(db_field, ForeignKey):
        related_model = db_field.related_model
        kwargs['widget'] = RelatedFieldWidgetCanAdd(
            related_model,
            related_url=f"{related_model._meta.model_name}_create"
        )
    return db_field.formfield(**kwargs)

# Base class to make every view use admin templates
class AdminTemplateMixin:
    template_name = "adminlike/change_form.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.model
        opts = model._meta

        context.update({
            "opts": opts,
            "app_label": opts.app_label,
            "model_name": opts.model_name,
            "verbose_name": opts.verbose_name,
            "name_plural": opts.verbose_name_plural,
            "media": self.get_form().media if hasattr(self, "get_form") else "",
        })
        return context

    def get_template_names(self):
        return([self.template_name])

class PreFillFromMixin:
    """
    Mixin that pre-fills form fields from URL query parameters.
    Any query parameter matching a field name will be used as initial value.
    """
    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self, 'fields'):
            # Iterate over URL parameters and pre-fill matching fields
            for field, value in self.request.GET.items():
                if field in self.fields:
                    initial[field] = value
        return initial

def make_crud_views(model):
    app_label = model._meta.app_label

    class List(AdminTemplateMixin, ListView):
        model = model
        paginate_by = 20
        template_name = "dpp/generic_list.html"
        # template_name = "adminlike/change_list.html"

    class Detail(AdminTemplateMixin, DetailView):
        model = model
        template_name = "dpp/generic_detail.html"
        # template_name = "adminlike/change_form.html"

    class Create(AdminTemplateMixin, PreFillFromMixin, CreateView):
        model = model
        fields = "__all__"
        template_name = "dpp/generic_form.html"
        # template_name = "adminlike/change_form.html"

        def get_form_class(self):
            return forms.modelform_factory(
                self.model,
                fields=self.fields,
                formfield_callback=customize_form
            )

        def form_valid(self, form):
            self.object = form.save(commit=False)
            self.object.save()
            form.save_m2m()
            return HttpResponseRedirect(self.get_success_url())

    class Update(AdminTemplateMixin, PreFillFromMixin, UpdateView):
        model = model
        fields = "__all__"
        template_name = "dpp/generic_form.html"
        # template_name = "adminlike/change_form.html"

    class Delete(DeleteView):
        model = model
        success_url = reverse_lazy(f"{app_label}:{model.__name__.lower()}_list")
        template_name = "dpp/confirm_delete.html"

    # Assign nice names
    List.__name__ = f"{model.__name__}ListView"
    Detail.__name__ = f"{model.__name__}DetailView"
    Create.__name__ = f"{model.__name__}CreateView"
    Update.__name__ = f"{model.__name__}UpdateView"
    Delete.__name__ = f"{model.__name__}DeleteView"

    # Wrap in a dictionary
    views_dict = {
        f"{model.__name__}List": List, 
        f"{model.__name__}Detail": Detail,
        f"{model.__name__}Create": Create,
        f"{model.__name__}Update": Update,
        f"{model.__name__}Delete": Delete,
    }
    return views_dict

# Generate all views automatically
views = {}
for model in [
    Institution, Company, Importer, ServiceOperator, Metadata, Document,
    Material, HazardousMaterial, CriticalRawMaterial, ProductType,
    Packaging, SecondaryProduct, Emission, Composition, Product,
    ProductionLine, Process, SharedProcess, Exchange,
    ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo,
    ServiceEvent, ServiceRecord, ReplacedComponents, EndOfLife,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, OldCircularityIndicator, CircularityIndicator,
    CircularityScore, CircularityEnabler,
]:
    views.update(make_crud_views(model))

# Make them importable
globals().update(views)

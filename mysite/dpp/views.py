from django.shortcuts import render, redirect
from django.contrib import messages
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

# Views based on the admin templates
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
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

# Base class to make every view use admin templates
class AdminTemplateMixin:
    template_name = "adminlike/change_form.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.model
        opts = model._meta

        context.update({
            "app_label": opts.app_label,
            "model_name": opts.model_name,
            "opts": opts,
            "verbose_name": opts.verbose_name,
            "verbose_name_plural": opts.verbose_name_plural,
            "has_add_permission": True, # or self.request.user.has_perm(...)
            "has_change_permission": True,
            "has_delete_permission": True,
            "has_view_permission": True,
            # This gives you all the form media (widgets, JS, CSS)
            "media": self.get_form().media if hasattr(self, "get_form") else "",
        })
        return context

    def get_template_names(self):
        return([self.template_name])

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

    class Create(AdminTemplateMixin, CreateView):
        model = model
        fields = "__all__"
        template_name = "dpp/generic_form.html"
        # template_name = "adminlike/change_form.html"

    class Update(AdminTemplateMixin, UpdateView):
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

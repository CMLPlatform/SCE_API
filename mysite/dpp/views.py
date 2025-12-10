from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from .models import ProductionLine
from api.serializers import ProductionLineSerializer
import json
import networkx as nx

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
from django.utils.safestring import mark_safe
from django.db.models import ForeignKey
from django.forms import widgets
from django.conf import settings
from django.urls import reverse, reverse_lazy
from .models import (
    Institution, Company, Importer, ServiceOperator, Metadata, Document,
    Material, HazardousMaterial, CriticalRawMaterial, ProductType,
    Packaging, SecondaryProduct, Emission, Composition, ProductItem,
    Activity, ProductionLine, Process, SharedProcess, BackgroundProcess, 
    Exchange, ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo,
    ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, CircularityIndicator,
    CircularityScore, CircularityEnabler,
)
from .forms import get_model_form_plus


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
        # form_class = FormWithAutoAdd

        def get_form_class(self):
            return get_model_form_plus(self.model, self.fields)
            # return forms.modelform_factory(
            #     self.model,
            #     fields=self.fields,
            #     formfield_callback=customize_form
            # )

        def form_valid(self, form):
            self.object = form.save(commit=False)
            self.object.save()
            form.save_m2m()
            return HttpResponseRedirect(self.get_success_url())

    class Update(AdminTemplateMixin, PreFillFromMixin, UpdateView):
        model = model
        # fields = "__all__"
        template_name = "dpp/generic_form.html"
        # template_name = "adminlike/change_form.html"
        # form_class = FormWithAutoAdd

        def get_form_class(self):
            return get_model_form_plus(self.model, self.fields)

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
    Packaging, SecondaryProduct, Emission, Composition, ProductItem,
    ProductionLine, Process, SharedProcess, Exchange,
    ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo,
    ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, CircularityIndicator,
    CircularityScore, CircularityEnabler,
]:
    views.update(make_crud_views(model))

# Make them importable
globals().update(views)


def create_process_graph(processes: list=[]):
    """ UNUSED
    Create a directed graph showing processes and their in/outputs.
    Returns graph data in a format suitable for visualization.
    """
    G = nx.DiGraph()
    
    # Add nodes and edges
    for process in processes:
        G.add_node(process.name, node_type='process', shape='square')
        
        # Add output node (functional_flow)
        if process.functional_flow:
            output_name = process.functional_flow.name
            G.add_node(output_name, node_type='output', shape='dot')
            G.add_edge(process.name, output_name)
        
        # Add environmental exchanges
        exchanges = process.env_exchanges.all()
        for exchange in exchanges:
            io_name = exchange.substance.name
            node_type = 'input' if exchange.exchange_type=='in' else 'output'
            G.add_node(io_name, node_type=node_type, shape='triangle')
            if node_type == 'output':
                G.add_edge(process.name, io_name)
            else:
                G.add_edge(io_name, process.name)
        # Add input nodes from Exchange table
        exchanges = process.prod_exchanges.all()
        for exchange in exchanges:
            io_name = exchange.product.name
            node_type = 'input' if exchange.exchange_type=='in' else 'output'
            G.add_node(io_name, node_type=node_type, shape='dot', size=0.1)
            G.add_edge(io_name, process.name)
            sources = Process.objects.filter(functional_flow=exchange.product)
            if sources:
                source_name = sources[0].name
                if source_name not in G.nodes:
                    G.add_node(source_name, node_type='process', shape='square')
                G.add_edge(source_name, io_name)

    # Convert to format suitable for D3.js or other visualization
    graph_dict = {'nodes': [], 'links': []}
    for node in G.nodes():
        graph_dict['nodes'].append({
            'id': node,
            'type': G.nodes[node].get('node_type', 'unknown'),
            'shape': G.nodes[node].get('shape', 'dot'),
        })
    
    for source, target in G.edges():
        graph_dict['links'].append({'source': source, 'target': target})
    print("Graph size", len(G.nodes), len(G.edges))
    return graph_dict

def create_flowchart(processes):
    """
    Build a Mermaid script for generating a flowchart of processes.

    The output string looks like:
        p1{{Electricity}}:::input --> a1
        a2(Steel mill):::outside -->|steel sheet| a1
        a2 -->e1((CO2)):::env
    outputs: final outputs, not used in `processes`
    suppliers: all production lines supplying input to `processes`
    background: all background processes supplying input to `processes`
    inputs: all products used by `processes` (or waste going out), but not produced anywhere
    """
    outputs = ProductType.objects.filter(
        produced_by__in=processes
        ).exclude(exchanged_by__process__in=processes
    ).distinct()
    inputs = ProductType.objects.filter(
        exchanged_by__process__in=processes
    ).distinct()
    exchanges = ProductExchange.objects.filter(product__produced_by__in=processes).filter(process__in=processes)
    suppliers = ProductionLine.objects.filter(final_product__in=inputs)
    background = BackgroundProcess.objects.filter(functional_flow__in=inputs)
    inputs = inputs.exclude(productionline__in=suppliers).exclude(produced_by_other__in=background).exclude(exchanged_by__in=exchanges)

    # Build Mermaid string
    lines = ["flowchart LR"]
    lines.append("    classDef process fill:aquamarine,stroke:teal,stroke-width:3px")
    lines.append("    classDef product fill:#4CAF50,color:white,stroke:green,stroke-width:3px")
    lines.append("    classDef input   fill:#2196F3,color:white,stroke:#1565c0,stroke-width:3px")
    lines.append("    classDef env     fill:#f44336,color:white,stroke:#c62828,stroke-width:3px")
    lines.append("    classDef outside fill:#9c27b0,color:white,stroke:#6a1b9a,stroke-width:3px")
    lines.append("")
    lines.append('    subgraph pl["`**Production line**`"]')

    # Print the core processes
    for proc in processes:
        lines.append(f"        a{proc.id}({proc.name}):::process")

    lines.append("    end")
    lines.append("    style pl #ffffde,stroke-width:3px,stroke-dasharray: 5 5")

    # Add unlinked products and emissions
    for prod in outputs:
        proc = prod.produced_by.first() #if prod.produced_by.exists() else None
        lines.append("    a%d --> ff%d{{%s}}:::product" % (proc.id, prod.id, prod.name))

    for exch in ProductExchange.objects.filter(product__in=inputs, process__in=processes):
        prod, proc = exch.product, exch.process
        if exch.exchange_type == 'in':
            lines.append('    p%d{{"%s"}}:::input -->a%d' % (prod.id, prod.name, proc.id))
        else:
            lines.append('    a%d -->p%d{{"%s"}}:::input' % (proc.id, prod.id, prod.name))
    for exch in EnvExchange.objects.filter(process__in=processes):
        if exch.exchange_type == 'in':
            lines.append('    e%d(("%s")):::env -->a%d' % (exch.id, exch.substance.name, exch.process.id))
        else:
            lines.append('    a%d --> e%d(("%s")):::env' % (exch.process.id, exch.id, exch.substance.name))
    # Add background processes
    for supp in suppliers:
        prod = supp.productionline.final_product
        for exch in ProductExchange.objects.filter(product=prod):
            if exch.exchange_type == 'in':
                lines.append(
                    f"    a{supp.id}({supp.operator.name}):::outside -->"
                    f"|{prod.name}| a{exch.process.id}"
                )
            else:
                lines.append(
                    f"    a{exch.process.id} -->|{prod.name}| "
                    f"a{supp.id}({supp.operator.name}):::outside"
                )

    for supp in background:
        prod = supp.productionline.final_product
        for exch in ProductExchange.objects.filter(product=prod):
            if exch.exchange_type == 'in':
                lines.append(
                    f"    a{supp.id}({supp.operator.name}):::outside -->"
                    f"|{prod.name}| a{exch.process.id}"
                )
            else:
                lines.append(
                    f"    a{exch.process.id} -->|{prod.name}| "
                    f"a{supp.id}({supp.operator.name}):::outside"
                )
    # Internal exchanges
    for exch in exchanges:
        orig = exch.product.produced_by.first()
        dest = exch.process
        lines.append("    a%d -->|%s| a%d" % (orig.id, exch.product.name, dest.id))

    return "\n".join(lines)

class ProductionLineDetailView(DetailView):
    model = ProductionLine
    template_name = 'dpp/productionline_detail.html' #'dpp/graph_test.html' #
    # context_object_name = 'production_line'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opts'] = model._meta
        # Add associated processes to the context
        context['processes'] = Process.objects.filter(
            production_line=self.object
        ).order_by('id')
        # Add a network graph
        graph_data = create_process_graph(context['processes'])
        context['graph_data'] = json.dumps(graph_data)
        # Add Mermaid flowchart
        mermaid_code = create_flowchart(context['processes'])
        context["mermaid_code"] = mermaid_code
        return context

class ProcessDetailView(DetailView):
    model = Process
    template_name = 'dpp/process_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opts'] = model._meta
        context['process'] = self.object
        # Add associated inputs and outputs to the context
        context['inputs'] = ProductExchange.objects.filter(
            process=self.object, exchange_type='in'
        )
        context['outputs'] = ProductExchange.objects.filter(
            process=self.object).exclude(exchange_type='in'
        )
        context['emissions'] = EnvExchange.objects.filter(
            process=self.object
        )
        return context

from django.contrib import messages
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from .models import (
    Institution, Company, Importer, ServiceOperator, Metadata, Facility,
    Document, Material, HazardousMaterial,
    Flow, ProductModel, ProductBatch, ProductItem, SecondaryProduct, 
    Emission, Composition, DppDetails,
    Activity, ManufacturingProcess, ProductionLine, Process, BackgroundProcess, 
    Exchange, ProductExchange, EnvExchange, Transport, ItemExchange,
    LifeCycleEvent, InspectionEvent, MaintenanceEvent, DisassemblyEvent,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, CircularityIndicator,
    CircularityScore, CircularityTracker, Publisher
)
from .forms import get_model_form_plus


def home(request):
    """Welcome page """
    latest_lines = ProductionLine.objects.order_by("-modified_at")[:5]
    if len(latest_lines) > 5:
        latest_lines = latest_lines[:5]
    context = {'latest_lines': latest_lines}
    return render(request, "dpp/index.html", context)

class AdminTemplateMixin:
    """Base class that prepares admin-like context."""
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

class PreFillFormMixin:
    """
    Mixin that pre-fills form fields from URL query parameters.
    Any query parameter matching a field name will be used as initial value.
    Also check if it's a popup, and define success_url
    """
    def get_initial(self):
        initial = super().get_initial()
        form_class = self.get_form_class()
        for field_name, value in self.request.GET.items():
            if field_name in form_class.base_fields:
                field = form_class.base_fields[field_name]
                # Convert to PK for relation fields
                if isinstance(field, (ModelChoiceField, ModelMultipleChoiceField)):
                    initial[field_name] = int(value)
                else:
                    initial[field_name] = value
        return initial
    
    def dispatch(self, request, *args, **kwargs):
        self.is_popup = request.GET.get('_popup', False)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_popup'] = self.is_popup
        return context
    
    def get_success_url(self):
        return reverse(
            f"{self.model._meta.app_label}:{self.model._meta.model_name}_list"
        )
    
    def form_valid(self, form):
        self.object = form.save()
        
        # Check if this is a popup request
        if self.is_popup:
            return HttpResponse(
                f'''
                <script type="text/javascript">
                    opener.dismissAddRelatedObjectPopup(window, "{self.object.pk}", "{self.object}");
                </script>
                '''
            )
        
        return super().form_valid(form)

def make_crud_views(model):
    app_label = model._meta.app_label

    class List(AdminTemplateMixin, ListView):
        model = model
        paginate_by = 40
        template_name = "dpp/generic_list.html"
        # template_name = "adminlike/change_list.html"

    class Detail(AdminTemplateMixin, DetailView):
        model = model
        template_name = "dpp/generic_detail.html"
        # template_name = "adminlike/change_form.html"

    class Create(AdminTemplateMixin, PreFillFormMixin, CreateView):
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

        # def form_valid(self, form):
        #     self.object = form.save(commit=False)
        #     self.object.save()
        #     form.save_m2m()
        #     return HttpResponseRedirect(self.get_success_url())

        # def get_success_url(self):  # Return to previous page
        #     return self.request.META.get('HTTP_REFERER')

    class Update(AdminTemplateMixin, PreFillFormMixin, UpdateView):
        model = model
        fields = "__all__"
        template_name = "dpp/generic_form.html"
        # template_name = "adminlike/change_form.html"
        # form_class = FormWithAutoAdd

        def get_form_class(self):
            return get_model_form_plus(self.model, self.fields)

    class Delete(AdminTemplateMixin, DeleteView):
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
    Institution, Company, Importer, ServiceOperator, Metadata, Facility,
    Document, Material, HazardousMaterial, Flow, ProductModel, ProductBatch,
    SecondaryProduct, Emission, Composition, ProductItem, DppDetails,
    Activity, ManufacturingProcess, ProductionLine, Process,
    Exchange, ProductExchange, EnvExchange, Transport, ItemExchange,
    LifeCycleEvent, InspectionEvent, MaintenanceEvent, DisassemblyEvent,
    ImpactCategory, SustainabilityEvaluation, SustainabilityScore,
    CircularityEvaluation, CircularityIndicator,
    CircularityScore, CircularityTracker,
]:
    views.update(make_crud_views(model))

# Make them importable
globals().update(views)


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
    outputs = Flow.objects.filter(
        produced_by__in=processes
        ).exclude(exchanged_by__process__in=processes
    ).distinct()
    inputs = Flow.objects.filter(
        exchanged_by__process__in=processes
    ).distinct()
    exchanges = ProductExchange.objects.filter(product__produced_by__in=processes).filter(process__in=processes)
    suppliers = ManufacturingProcess.objects.filter(functional_flow__in=inputs)
    inputs = inputs.exclude(manufacturing_info__in=suppliers).exclude(exchanged_by__in=exchanges)

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
        proc = prod.produced_by
        lines.append("    a%d --> ff%d{{%s}}:::product" % (proc.id, prod.id, prod))

    for exch in ProductExchange.objects.filter(product__in=inputs, process__in=processes):
        prod, proc = exch.product, exch.process
        if exch.direction == 'in':
            lines.append('    p%d{{"%s"}}:::input -->a%d' % (prod.id, prod, proc.id))
        else:
            lines.append('    a%d -->p%d{{"%s"}}:::input' % (proc.id, prod.id, prod))
    for exch in EnvExchange.objects.filter(process__in=processes):
        if exch.direction == 'in':
            lines.append('    e%d(("%s")):::env -->a%d' % (exch.id, exch.substance.name, exch.process.id))
        else:
            lines.append('    a%d --> e%d(("%s")):::env' % (exch.process.id, exch.id, exch.substance.name))
    # Add background processes
    for supp in suppliers:
        prod = supp.functional_flow
        for exch in ProductExchange.objects.filter(product=prod):
            if exch.direction == 'in':
                lines.append(
                    f"    a{supp.id}({prod}):::outside --> a{exch.process.id}"
                    # f"    a{supp.id}({supp.facility.operator}):::outside -->"
                    # f"|{prod}| a{exch.process.id}"
                )
            else:
                lines.append(
                    f"    a{exch.process.id} --> a{supp.id}({prod}):::outside"
                )
    # Internal exchanges
    for exch in exchanges:
        orig = exch.product.produced_by
        dest = exch.process
        lines.append("    a%d -->|%s| a%d" % (orig.id, exch.product, dest.id))

    return "\n".join(lines)

class ProductionLineDetailView(DetailView):
    model = ProductionLine
    template_name = 'dpp/productionline_detail.html' #'dpp/graph_test.html' #
    # context_object_name = 'production_line'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opts'] = self.model._meta
        # Add associated processes to the context
        context['processes'] = Process.objects.filter(
            production_line=self.object
        ).order_by('id')
        context['transport_list'] = self.object.transport.all()
        # Check for warnings
        context['warnings'] = self.object.check_unused_outputs()
        # Add Mermaid flowchart
        mermaid_code = create_flowchart(context['processes'])
        context["mermaid_code"] = mermaid_code
        # Find Publisher (if available)
        try:
            context['publisher'] = self.object.publisher
        except Publisher.DoesNotExist:
            context['publisher'] = None
        return context
    
    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'create_publisher':
            # Get or create Publisher
            publisher, created = Publisher.objects.get_or_create(
                production_line=self.get_object()
            )
            # Redirect to Publisher detail view
            return redirect('publisher_detail', pk=publisher.pk)
        
        return super().post(request, *args, **kwargs)

class ProcessDetailView(AdminTemplateMixin, DetailView):
    model = Process
    template_name = 'dpp/process_detail.html'
    FLOW_ICONS = {
        'prod':  '🧩',    # Component of the product
        'cons':  '🧃',    # Consumable
        'ener':  '🔥',    # Electricity or heat ⚡
        'util':  '⚙️',    # Utility or equipment
        'serv':  '🧑‍🔧',    # Service
        'pack':  '📦',    # Packaging
        'react': '⚗️',    # Reactant 🧪
        'waste': '🗑️',    # Waste
        'texts': ProductExchange.FLOW_TYPES,
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process'] = self.object
        # Add associated inputs and outputs to the context
        context['inputs'] = ProductExchange.objects.filter(
            process=self.object, direction='in'
        )
        context['outputs'] = ProductExchange.objects.filter(
            process=self.object).exclude(direction='in'
        )
        context['emissions'] = EnvExchange.objects.filter(
            process=self.object
        )
        context['flow_icons'] = self.FLOW_ICONS
        return context

class ProductDetailView(AdminTemplateMixin, DetailView):
    model = ProductModel
    template_name = 'dpp/product_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materials'] = self.object.get_composition()
        context['manufacturer'] = self.object.manufacturer
        context['missing_bom'] = self.object.find_missing_bom()
        if hasattr(self.object, 'produced_by'):
            context['produced_by'] = self.object.produced_by
        else:
            context['produced_by'] = None
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'recalculate' in request.POST:
            self.object.get_composition(recalculate=True)
        return redirect('dpp:product_detail', pk=self.object.pk)

class TransportSubsetView(AdminTemplateMixin, ListView):
    template_name = "dpp/generic_list.html"
    model = Transport

    def get_queryset(self):
        pl = get_object_or_404(ProductionLine, pk=self.kwargs['productionline'])
        queryset = Transport.objects.filter(production_line=pl)
        if not queryset:
            pl.create_transport()
            queryset = Transport.objects.filter(production_line=pl)
        return queryset

class FlowCreateView(CreateView):
    model = Flow
    template_name = "dpp/create_flow.html"
    fields = []  # No user-editable fields

class PublisherDetailView(AdminTemplateMixin, DetailView):
    model = Publisher
    template_name = "dpp/publisher_detail.html"
    
    def post(self, request, *args, **kwargs):
        publisher = self.get_object()
        action = request.POST.get('action')
        
        if action == 'run_all':
            success = publisher.run_from_step(1)
            if success:
                messages.success(request, "All steps completed successfully!")
            else:
                messages.error(request, f"Error: {publisher.error_message}")
        
        elif action == 'rerun_step':
            step = int(request.POST.get('step'))
            success = publisher.run_from_step(step)
            if success:
                messages.success(request, f"Steps {step}-5 completed successfully!")
            else:
                messages.error(request, f"Error: {publisher.error_message}")
        
        elif action == 'add_subcomponents':
            # Special action for step 3
            publisher.production_line.final_product.add_subcomponents()
            messages.success(request, "Subcomponents added!")
        
        elif action == 'publish':
            publisher.create_dpps()
            messages.success(request, f"{publisher.amount} DPPs created!")
        
        return redirect('dpp:publisher_detail', pk=publisher.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publisher = self.get_object()
        
        # Build step status for template
        context['steps'] = [
            {
                'number': i,
                'name': Publisher.STEP_NAMES[i],
                'completed': i <= publisher.status,
                'can_rerun': i <= publisher.status + 1
            }
            for i in range(1, 6)
        ]
        return context

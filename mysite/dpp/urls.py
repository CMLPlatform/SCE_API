from django.urls import path
from .models import *

from . import views

app_name = "dpp"

urlpatterns = [
    path("welcome/", views.home, name="home"),
    path('transports/<int:productionline>/', views.TransportSubsetView.as_view(), name='transport_subset'),
    path('flow/add/', views.FlowCreateView.as_view(), name='flow_add'),
    path("publisher/<int:pk>/update/", views.PublisherUpdateView.as_view(), name='publisher_update'),
    path('final/<uuid:pk>/', views.DppFullView.as_view(), name='dpp_full'),
]

# Models for which a custom DetailView is defined (named as ModelNameDetailView)
CUSTOM_DETAIL = {ProductionLine, Process, ProductModel, Publisher}

for model in [Institution, Company, Importer, ServiceOperator, Metadata, Document, Facility, Material, HazardousMaterial, Flow, ProductModel, ProductBatch, SecondaryProduct, DppDetails, ProductProperties, Emission, Composition, ProductItem, Activity, ProductionLine, Process, Exchange, ProductExchange, EnvExchange, LifeCycleEvent, InspectionEvent, MaintenanceEvent, DisassemblyEvent, ItemExchange, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityTracker, Transport]:
    Name = model.__name__
    name = model.__name__.lower()
    pk = "uuid:pk" if isinstance(model._meta.pk, models.UUIDField) else "int:pk"
    detail_name = Name + ("DetailView" if model in CUSTOM_DETAIL else "Detail")
    urlpatterns += [
        path(f"{name}/", getattr(views, f"{Name}List").as_view(), name=f"{name}_list"),
        path(f"{name}/add/", getattr(views, f"{Name}Create").as_view(), name=f"{name}_add"),
        path(f"{name}/<{pk}>/", getattr(views, detail_name).as_view(), name=f"{name}_detail"),
        path(f"{name}/<{pk}>/update/", getattr(views, f"{Name}Update").as_view(), name=f"{name}_update"),
        path(f"{name}/<{pk}>/delete/", getattr(views, f"{Name}Delete").as_view(), name=f"{name}_delete"),
    ]

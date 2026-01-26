from django.urls import path
from .models import *

from . import views

app_name = "dpp"

urlpatterns = [
    path("welcome", views.home, name="home"),
    path('production-line/<int:pk>/', views.ProductionLineDetailView.as_view(), name='production_line_detail'),
    path('process/<int:pk>/', views.ProcessDetailView.as_view(), name='process_detail'),
    path('product/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('transports/<int:productionline>/', views.TransportSubsetView.as_view(), name='transport_subset'),
    path('flow/add/', views.FlowCreateView.as_view(), name='flow_add'),
]

# urlpatterns = []
for model in [Institution, Company, Importer, ServiceOperator, Metadata, Document, Material, HazardousMaterial, Flow, ProductModel, ProductBatch, SecondaryProduct, DppDetails, Emission, Composition, ProductItem, Activity, ProductionLine, Process, SharedProcess, Exchange, ProductExchange, EnvExchange, LifeCycleEvent, InspectionEvent, MaintenanceEvent, DisassemblyEvent, ItemExchange, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityTracker, Transport]:
    name = model.__name__.lower()
    urlpatterns += [
        path(f"{name}/", getattr(views, f"{model.__name__}List").as_view(), name=f"{name}_list"),
        path(f"{name}/add/", getattr(views, f"{model.__name__}Create").as_view(), name=f"{name}_add"),
        path(f"{name}/<int:pk>/", getattr(views, f"{model.__name__}Detail").as_view(), name=f"{name}_detail"),
        path(f"{name}/<int:pk>/update/", getattr(views, f"{model.__name__}Update").as_view(), name=f"{name}_update"),
        path(f"{name}/<int:pk>/delete/", getattr(views, f"{model.__name__}Delete").as_view(), name=f"{name}_delete"),
    ]
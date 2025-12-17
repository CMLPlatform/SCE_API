from django.urls import path
from .models import *

from . import views

app_name = "dpp"

urlpatterns = [
    path("welcome", views.home, name="home"),
    path("production-lines/create/", views.production_line_create, name="production_line_create"),
    path("production-lines/<int:pk>/edit/", views.production_line_edit, name="production_line_edit"),
    path('production-line/<int:pk>/', views.ProductionLineDetailView.as_view(), name='production_line_detail'),
    path('process/<int:pk>/', views.ProcessDetailView.as_view(), name='process_detail'),
]

# urlpatterns = []
for model in [Institution, Company, Importer, ServiceOperator, Metadata, Document, Material, HazardousMaterial, ProductModel, ProductBatch, SecondaryProduct, DppDetails, Emission, Composition, ProductItem, Activity, ProductionLine, Process, SharedProcess, Exchange, ProductExchange, EnvExchange, ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityEnabler]:
    name = model.__name__.lower()
    urlpatterns += [
        path(f"{name}/", getattr(views, f"{model.__name__}List").as_view(), name=f"{name}_list"),
        path(f"{name}/add/", getattr(views, f"{model.__name__}Create").as_view(), name=f"{name}_add"),
        path(f"{name}/<int:pk>/", getattr(views, f"{model.__name__}Detail").as_view(), name=f"{name}_detail"),
        path(f"{name}/<int:pk>/update/", getattr(views, f"{model.__name__}Update").as_view(), name=f"{name}_update"),
        path(f"{name}/<int:pk>/delete/", getattr(views, f"{model.__name__}Delete").as_view(), name=f"{name}_delete"),
    ]
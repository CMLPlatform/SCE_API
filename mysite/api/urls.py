from django.urls import path, include
from drf_spectacular.utils import extend_schema
from rest_framework.routers import DefaultRouter

from . import views

# Routes grouped by concern. Each group is one tag (section) in the
# OpenAPI docs at /schema/swagger/ and /schema/redoc/.
ROUTE_GROUPS = {
    "Organizations": [
        ("organization", views.OrganizationViewSet, "Organization"),
        ("institution", views.InstitutionViewSet, "Institution"),
        ("company", views.CompanyViewSet, "Company"),
        ("importer", views.ImporterViewSet, "Importer"),
        ("serviceoperator", views.ServiceOperatorViewSet, "ServiceOperator"),
    ],
    "Documents": [
        ("instruction", views.InstructionViewSet, "Instruction"),
        ("document", views.DocumentViewSet, "Document"),
    ],
    "Products": [
        ("productmodel", views.ProductModelViewSet, "ProductModel"),
        ("productbatch", views.ProductBatchViewSet, "ProductBatch"),
        ("secondaryproduct", views.SecondaryProductViewSet, "SecondaryProduct"),
        ("productitem", views.ProductItemViewSet, "ProductItem"),
        ("productproperties", views.ProductPropertiesViewSet, "ProductProperties"),
        ("dppdetails", views.DppDetailsViewSet, "DppDetails"),
        ("metadata", views.MetadataViewSet, "Metadata"),
        ("alias", views.AliasViewSet, "Alias"),
    ],
    "Materials": [
        ("material", views.MaterialViewSet, "Material"),
        ("hazardousmaterial", views.HazardousMaterialViewSet, "HazardousMaterial"),
        ("composition", views.CompositionViewSet, "Composition"),
    ],
    "Processes and inventory": [
        ("activity", views.ActivityViewSet, "Activity"),
        ("manufacturingprocess", views.ManufacturingProcessViewSet, "ManufacturingProcess"),
        ("productionline", views.ProductionLineViewSet, "ProductionLine"),
        ("process", views.ProcessViewSet, "Process"),
        ("backgroundprocess", views.BackgroundProcessViewSet, "BackgroundProcess"),
        ("productexchange", views.ProductExchangeViewSet, "ProductExchange"),
        ("envexchange", views.EnvExchangeViewSet, "EnvExchange"),
        ("emission", views.EmissionViewSet, "Emission"),
        ("transport", views.TransportViewSet, "Transport"),
    ],
    "Life cycle events": [
        ("lifecycleevent", views.LifeCycleEventViewSet, "LifeCycleEvent"),
        ("inspectionevent", views.InspectionEventViewSet, "InspectionEvent"),
        ("maintenanceevent", views.MaintenanceEventViewSet, "MaintenanceEvent"),
        ("disassemblyevent", views.DisassemblyEventViewSet, "DisassemblyEvent"),
        ("itemexchange", views.ItemExchangeViewSet, "ItemExchange"),
    ],
    "Sustainability assessment": [
        ("indicatorset", views.IndicatorSetViewSet, "IndicatorSet"),
        ("impactcategory", views.ImpactCategoryViewSet, "ImpactCategory"),
        ("impactindicator", views.ImpactIndicatorViewSet, "ImpactIndicator"),
        ("sustainabilityevaluation", views.SustainabilityEvaluationViewSet, "SustainabilityEvaluation"),
        ("sustainabilityscore", views.SustainabilityScoreViewSet, "SustainabilityScore"),
    ],
    "Circularity assessment": [
        ("circularityevaluation", views.CircularityEvaluationViewSet, "CircularityEvaluation"),
        ("circularityindicator", views.CircularityIndicatorViewSet, "CircularityIndicator"),
        ("circularityscore", views.CircularityScoreViewSet, "CircularityScore"),
        ("circularityenabler", views.CircularityTrackerViewSet, "CircularityTracker"),
    ],
}

router = DefaultRouter()
for tag, routes in ROUTE_GROUPS.items():
    for prefix, viewset, basename in routes:
        router.register(prefix, extend_schema(tags=[tag])(viewset), basename=basename)

urlpatterns = [
    path(r'', include(router.urls)),
]

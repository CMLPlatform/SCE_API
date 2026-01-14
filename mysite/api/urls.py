from django.contrib import admin
from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'organization', views.OrganizationViewSet, basename='Organization')
router.register(r'institution', views.InstitutionViewSet, basename='Institution')
router.register(r'company', views.CompanyViewSet, basename='Company')
router.register(r'importer', views.ImporterViewSet, basename='Importer')
router.register(r'serviceoperator', views.ServiceOperatorViewSet, basename='ServiceOperator')
router.register(r'metadata', views.MetadataViewSet, basename='Metadata')
router.register(r'instruction', views.InstructionViewSet, basename='Instruction')
router.register(r'document', views.DocumentViewSet, basename='Document')
router.register(r'material', views.MaterialViewSet, basename='Material')
router.register(r'hazardousmaterial', views.HazardousMaterialViewSet, basename='HazardousMaterial')
router.register(r'productmodel', views.ProductModelViewSet, basename='ProductModel')
router.register(r'productbatch', views.ProductBatchViewSet, basename='ProductBatch')
router.register(r'productproperties', views.ProductPropertiesViewSet, basename='ProductProperties')
router.register(r'dppdetails', views.DppDetailsViewSet, basename='DppDetails')
router.register(r'secondaryproduct', views.SecondaryProductViewSet, basename='SecondaryProduct')
router.register(r'emission', views.EmissionViewSet, basename='Emission')
router.register(r'composition', views.CompositionViewSet, basename='Composition')
router.register(r'productitem', views.ProductItemViewSet, basename='ProductItem')
router.register(r'activity', views.ActivityViewSet, basename='Activity')
router.register(r'manufacturingprocess', views.ManufacturingProcessViewSet, basename='ManufacturingProcess')
router.register(r'productionline', views.ProductionLineViewSet, basename='ProductionLine')
router.register(r'process', views.ProcessViewSet, basename='Process')
router.register(r'sharedprocess', views.SharedProcessViewSet, basename='SharedProcess')
router.register(r'backgroundprocess', views.BackgroundProcessViewSet, basename='BackgroundProcess')
router.register(r'productexchange', views.ProductExchangeViewSet, basename='ProductExchange')
router.register(r'envexchange', views.EnvExchangeViewSet, basename='EnvExchange')
router.register(r'alias', views.AliasViewSet, basename='Alias')
router.register(r'transport', views.TransportViewSet, basename='Transport')
router.register(r'lifecycleevent', views.LifeCycleEventViewSet, basename='LifeCycleEvent')
router.register(r'inspectionevent', views.InspectionEventViewSet, basename='InspectionEvent')
router.register(r'maintenanceevent', views.MaintenanceEventViewSet, basename='MaintenanceEvent')
router.register(r'itemexchange', views.ItemExchangeViewSet, basename='ItemExchange')
router.register(r'disassemblyevent', views.DisassemblyEventViewSet, basename='DisassemblyEvent')
router.register(r'indicatorset', views.IndicatorSetViewSet, basename='IndicatorSet')
router.register(r'impactcategory', views.ImpactCategoryViewSet, basename='ImpactCategory')
router.register(r'impactindicator', views.ImpactIndicatorViewSet, basename='ImpactIndicator')
router.register(r'sustainabilityevaluation', views.SustainabilityEvaluationViewSet, basename='SustainabilityEvaluation')
router.register(r'sustainabilityscore', views.SustainabilityScoreViewSet, basename='SustainabilityScore')
router.register(r'circularityevaluation', views.CircularityEvaluationViewSet, basename='CircularityEvaluation')
router.register(r'circularityindicator', views.CircularityIndicatorViewSet, basename='CircularityIndicator')
router.register(r'circularityscore', views.CircularityScoreViewSet, basename='CircularityScore')
router.register(r'circularityenabler', views.CircularityTrackerViewSet, basename='CircularityTracker')


urlpatterns = [
    path(r'', include(router.urls)),
]

"""
urlpatterns = [
    path('productionlines/', views.ProductionLinesListCreate.as_view(), name="production-view-create"),
    path('productionlines/<int:pk>', views.ProductionLineHandle.as_view(), name="handle-productionline"),
    path('processes/', views.ProcessCreate.as_view(), name="process-view-create"),
    path('processes/search/', views.ProcessSearch.as_view(), name='process-search'),
]
"""
from django.db import models as dj_models
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.viewsets import ModelViewSet
from dpp.models import *
from dpp.permissions import can_access, filter_owned
from .serializers import *


class OwnedModelViewSet(ModelViewSet):
    """ModelViewSet that applies the ownership rules of dpp.permissions:
    users only see their own production lines (and what belongs to them),
    cannot link new data to another user's production line, and become
    the owner of production lines they create.
    Login is required by default (see REST_FRAMEWORK in settings).
    """
    def get_queryset(self):
        return filter_owned(super().get_queryset(), self.request.user)

    def _check_references(self, serializer):
        for value in serializer.validated_data.values():
            if isinstance(value, dj_models.Model) and not can_access(self.request.user, value):
                raise PermissionDenied("You cannot link to another user's data.")

    def perform_create(self, serializer):
        self._check_references(serializer)
        model = self.get_queryset().model
        if any(f.name == "created_by" for f in model._meta.fields):
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        self._check_references(serializer)
        serializer.save()


class PublicReadStaffWrite(BasePermission):
    """Anyone may read; only staff may change."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

class OrganizationViewSet(OwnedModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

class InstitutionViewSet(OwnedModelViewSet):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer

class CompanyViewSet(OwnedModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class ImporterViewSet(OwnedModelViewSet):
    queryset = Importer.objects.all()
    serializer_class = ImporterSerializer

class ServiceOperatorViewSet(OwnedModelViewSet):
    queryset = ServiceOperator.objects.all()
    serializer_class = ServiceOperatorSerializer

class MetadataViewSet(OwnedModelViewSet):
    """Published DPPs: public to read, only staff can change them."""
    queryset = Metadata.objects.all()
    serializer_class = MetadataSerializer
    permission_classes = [PublicReadStaffWrite]

    def get_queryset(self):
        # Public by design: do not limit to the user's own DPPs
        return self.queryset.all()

class InstructionViewSet(OwnedModelViewSet):
    queryset = Instruction.objects.all()
    serializer_class = InstructionSerializer

class DocumentViewSet(OwnedModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

class MaterialViewSet(OwnedModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer

class HazardousMaterialViewSet(OwnedModelViewSet):
    queryset = HazardousMaterial.objects.all()
    serializer_class = HazardousMaterialSerializer

class FlowViewSet(OwnedModelViewSet):
    queryset = Flow.objects.all()
    serializer_class = FlowSerializer

class ProductModelViewSet(OwnedModelViewSet):
    queryset = ProductModel.objects.all()
    serializer_class = ProductModelSerializer

class ProductBatchViewSet(OwnedModelViewSet):
    queryset = ProductBatch.objects.all()
    serializer_class = ProductBatchSerializer

class ProductPropertiesViewSet(OwnedModelViewSet):
    queryset = ProductProperties.objects.all()
    serializer_class = ProductPropertiesSerializer

class DppDetailsViewSet(OwnedModelViewSet):
    queryset = DppDetails.objects.all()
    serializer_class = DppDetailsSerializer

class SecondaryProductViewSet(OwnedModelViewSet):
    queryset = SecondaryProduct.objects.all()
    serializer_class = SecondaryProductSerializer

class EmissionViewSet(OwnedModelViewSet):
    queryset = Emission.objects.all()
    serializer_class = EmissionSerializer

class CompositionViewSet(OwnedModelViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionSerializer

class ProductItemViewSet(OwnedModelViewSet):
    queryset = ProductItem.objects.all()
    serializer_class = ProductItemSerializer

class ActivityViewSet(OwnedModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

class ManufacturingProcessViewSet(OwnedModelViewSet):
    queryset = ManufacturingProcess.objects.all()
    serializer_class = ManufacturingProcessSerializer

class ProductionLineViewSet(OwnedModelViewSet):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer

class ProcessViewSet(OwnedModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer

class BackgroundProcessViewSet(OwnedModelViewSet):
    queryset = BackgroundProcess.objects.all()
    serializer_class = BackgroundProcessSerializer

class ProductExchangeViewSet(OwnedModelViewSet):
    queryset = ProductExchange.objects.all()
    serializer_class = ProductExchangeSerializer

class EnvExchangeViewSet(OwnedModelViewSet):
    queryset = EnvExchange.objects.all()
    serializer_class = EnvExchangeSerializer

class AliasViewSet(OwnedModelViewSet):
    queryset = Alias.objects.all()
    serializer_class = AliasSerializer

class TransportViewSet(OwnedModelViewSet):
    queryset = Transport.objects.all()
    serializer_class = TransportSerializer

class LifeCycleEventViewSet(OwnedModelViewSet):
    queryset = LifeCycleEvent.objects.all()
    serializer_class = LifeCycleEventSerializer

class InspectionEventViewSet(OwnedModelViewSet):
    queryset = InspectionEvent.objects.all()
    serializer_class = InspectionEventSerializer

class MaintenanceEventViewSet(OwnedModelViewSet):
    queryset = MaintenanceEvent.objects.all()
    serializer_class = MaintenanceEventSerializer

class ItemExchangeViewSet(OwnedModelViewSet):
    queryset = ItemExchange.objects.all()
    serializer_class = ItemExchangeSerializer

class DisassemblyEventViewSet(OwnedModelViewSet):
    queryset = DisassemblyEvent.objects.all()
    serializer_class = DisassemblyEventSerializer

class IndicatorSetViewSet(OwnedModelViewSet):
    queryset = IndicatorSet.objects.all()
    serializer_class = IndicatorSetSerializer

class ImpactCategoryViewSet(OwnedModelViewSet):
    queryset = ImpactCategory.objects.all()
    serializer_class = ImpactCategorySerializer

class ImpactIndicatorViewSet(OwnedModelViewSet):
    queryset = ImpactIndicator.objects.all()
    serializer_class = ImpactIndicatorSerializer

class SustainabilityEvaluationViewSet(OwnedModelViewSet):
    queryset = SustainabilityEvaluation.objects.all()
    serializer_class = SustainabilityEvaluationSerializer

class SustainabilityScoreViewSet(OwnedModelViewSet):
    queryset = SustainabilityScore.objects.all()
    serializer_class = SustainabilityScoreSerializer

class CircularityEvaluationViewSet(OwnedModelViewSet):
    queryset = CircularityEvaluation.objects.all()
    serializer_class = CircularityEvaluationSerializer

class CircularityIndicatorViewSet(OwnedModelViewSet):
    queryset = CircularityIndicator.objects.all()
    serializer_class = CircularityIndicatorSerializer

class CircularityScoreViewSet(OwnedModelViewSet):
    queryset = CircularityScore.objects.all()
    serializer_class = CircularityScoreSerializer

class CircularityTrackerViewSet(OwnedModelViewSet):
    queryset = CircularityTracker.objects.all()
    serializer_class = CircularityTrackerSerializer

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from dpp.models import *
from .serializers import *

# This view allows to see all Production Lines.
class ProductionLinesListCreate(generics.ListCreateAPIView):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer
    
    # Delete all Production Lines
    def delete(self, request, *args, **kwargs):
        ProductionLine.objects.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Retrieve, update or delete a specific Production Line by its ID
class ProductionLineHandle(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer
    lookup_field = 'pk' # Primary key

# Create a new Process and view all
class ProcessCreate(generics.CreateAPIView):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer

class ProcessSearch(APIView):
    """GET  /api/processes/search/?q=foobar
    """
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {"detail": "Parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = Process.objects.filter(process_name__icontains=query)
        serializer = ProcessSerializer(results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizationViewSet(ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

class InstitutionViewSet(ModelViewSet):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer

class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class ImporterViewSet(ModelViewSet):
    queryset = Importer.objects.all()
    serializer_class = ImporterSerializer

class ServiceOperatorViewSet(ModelViewSet):
    queryset = ServiceOperator.objects.all()
    serializer_class = ServiceOperatorSerializer

class MetadataViewSet(ModelViewSet):
    queryset = Metadata.objects.all()
    serializer_class = MetadataSerializer

class InstructionViewSet(ModelViewSet):
    queryset = Instruction.objects.all()
    serializer_class = InstructionSerializer

class DocumentViewSet(ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

class MaterialViewSet(ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer

class HazardousMaterialViewSet(ModelViewSet):
    queryset = HazardousMaterial.objects.all()
    serializer_class = HazardousMaterialSerializer

class FlowViewSet(ModelViewSet):
    queryset = Flow.objects.all()
    serializer_class = FlowSerializer

class ProductModelViewSet(ModelViewSet):
    queryset = ProductModel.objects.all()
    serializer_class = ProductModelSerializer

class ProductBatchViewSet(ModelViewSet):
    queryset = ProductBatch.objects.all()
    serializer_class = ProductBatchSerializer

class ProductPropertiesViewSet(ModelViewSet):
    queryset = ProductProperties.objects.all()
    serializer_class = ProductPropertiesSerializer

class DppDetailsViewSet(ModelViewSet):
    queryset = DppDetails.objects.all()
    serializer_class = DppDetailsSerializer

class SecondaryProductViewSet(ModelViewSet):
    queryset = SecondaryProduct.objects.all()
    serializer_class = SecondaryProductSerializer

class EmissionViewSet(ModelViewSet):
    queryset = Emission.objects.all()
    serializer_class = EmissionSerializer

class CompositionViewSet(ModelViewSet):
    queryset = Composition.objects.all()
    serializer_class = CompositionSerializer

class ProductItemViewSet(ModelViewSet):
    queryset = ProductItem.objects.all()
    serializer_class = ProductItemSerializer

class ActivityViewSet(ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

class ManufacturingProcessViewSet(ModelViewSet):
    queryset = ManufacturingProcess.objects.all()
    serializer_class = ManufacturingProcessSerializer

class ProductionLineViewSet(ModelViewSet):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer

class ProcessViewSet(ModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer

class BackgroundProcessViewSet(ModelViewSet):
    queryset = BackgroundProcess.objects.all()
    serializer_class = BackgroundProcessSerializer

class ProductExchangeViewSet(ModelViewSet):
    queryset = ProductExchange.objects.all()
    serializer_class = ProductExchangeSerializer

class EnvExchangeViewSet(ModelViewSet):
    queryset = EnvExchange.objects.all()
    serializer_class = EnvExchangeSerializer

class AliasViewSet(ModelViewSet):
    queryset = Alias.objects.all()
    serializer_class = AliasSerializer

class TransportViewSet(ModelViewSet):
    queryset = Transport.objects.all()
    serializer_class = TransportSerializer

class LifeCycleEventViewSet(ModelViewSet):
    queryset = LifeCycleEvent.objects.all()
    serializer_class = LifeCycleEventSerializer

class InspectionEventViewSet(ModelViewSet):
    queryset = InspectionEvent.objects.all()
    serializer_class = InspectionEventSerializer

class MaintenanceEventViewSet(ModelViewSet):
    queryset = MaintenanceEvent.objects.all()
    serializer_class = MaintenanceEventSerializer

class ItemExchangeViewSet(ModelViewSet):
    queryset = ItemExchange.objects.all()
    serializer_class = ItemExchangeSerializer

class DisassemblyEventViewSet(ModelViewSet):
    queryset = DisassemblyEvent.objects.all()
    serializer_class = DisassemblyEventSerializer

class IndicatorSetViewSet(ModelViewSet):
    queryset = IndicatorSet.objects.all()
    serializer_class = IndicatorSetSerializer

class ImpactCategoryViewSet(ModelViewSet):
    queryset = ImpactCategory.objects.all()
    serializer_class = ImpactCategorySerializer

class ImpactIndicatorViewSet(ModelViewSet):
    queryset = ImpactIndicator.objects.all()
    serializer_class = ImpactIndicatorSerializer

class SustainabilityEvaluationViewSet(ModelViewSet):
    queryset = SustainabilityEvaluation.objects.all()
    serializer_class = SustainabilityEvaluationSerializer

class SustainabilityScoreViewSet(ModelViewSet):
    queryset = SustainabilityScore.objects.all()
    serializer_class = SustainabilityScoreSerializer

class CircularityEvaluationViewSet(ModelViewSet):
    queryset = CircularityEvaluation.objects.all()
    serializer_class = CircularityEvaluationSerializer

class CircularityIndicatorViewSet(ModelViewSet):
    queryset = CircularityIndicator.objects.all()
    serializer_class = CircularityIndicatorSerializer

class CircularityScoreViewSet(ModelViewSet):
    queryset = CircularityScore.objects.all()
    serializer_class = CircularityScoreSerializer

class CircularityTrackerViewSet(ModelViewSet):
    queryset = CircularityTracker.objects.all()
    serializer_class = CircularityTrackerSerializer

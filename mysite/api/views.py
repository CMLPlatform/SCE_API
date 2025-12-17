from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from dpp.models import ProductionLine, Process
from .serializers import ProductionLineSerializer, ProcessSerializer

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

from rest_framework.viewsets import ModelViewSet
from dpp.models import Institution, Company, Importer, ServiceOperator, Metadata, Document, Material, HazardousMaterial, ProductModel, ProductBatch, SecondaryProduct, Emission, Composition, ProductItem, ProductionLine, Process, SharedProcess, Exchange, ProductExchange, EnvExchange, ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityEnabler, CircularityTracker
from .serializers import InstitutionSerializer, CompanySerializer, ImporterSerializer, ServiceOperatorSerializer, MetadataSerializer, DocumentSerializer, MaterialSerializer, HazardousMaterialSerializer, ProductModelSerializer, ProductBatchSerializer, SecondaryProductSerializer, EmissionSerializer, CompositionSerializer, ProductSerializer, ProductionLineSerializer, ProcessSerializer, SharedProcessSerializer, ProductExchangeSerializer, EnvExchangeSerializer, ServiceEventSerializer, ServiceRecordSerializer,  ReplacedComponentSerializer, EndOfLifeSerializer, ImpactCategorySerializer, SustainabilityEvaluationSerializer, SustainabilityScoreSerializer, CircularityEvaluationSerializer, CircularityIndicatorSerializer, CircularityScoreSerializer, CircularityEnablerSerializer


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

class DocumentViewSet(ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

class MaterialViewSet(ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer

class HazardousMaterialViewSet(ModelViewSet):
    queryset = HazardousMaterial.objects.all()
    serializer_class = HazardousMaterialSerializer

class ProductModelViewSet(ModelViewSet):
    queryset = ProductModel.objects.all()
    serializer_class = ProductModelSerializer

class ProductBatchViewSet(ModelViewSet):
    queryset = ProductBatch.objects.all()
    serializer_class = ProductBatchSerializer

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
    serializer_class = ProductSerializer

class ProductionLineViewSet(ModelViewSet):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer

class ProcessViewSet(ModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer

class SharedProcessViewSet(ModelViewSet):
    queryset = SharedProcess.objects.all()
    serializer_class = SharedProcessSerializer

class ProductExchangeViewSet(ModelViewSet):
    queryset = ProductExchange.objects.all()
    serializer_class = ProductExchangeSerializer

class EnvExchangeViewSet(ModelViewSet):
    queryset = EnvExchange.objects.all()
    serializer_class = EnvExchangeSerializer

class ServiceEventViewSet(ModelViewSet):
    queryset = ServiceEvent.objects.all()
    serializer_class = ServiceEventSerializer

class ServiceRecordViewSet(ModelViewSet):
    queryset = ServiceRecord.objects.all()
    serializer_class = ServiceRecordSerializer

class  ReplacedComponentViewSet(ModelViewSet):
    queryset = ReplacedComponent.objects.all()
    serializer_class =  ReplacedComponentSerializer

class EndOfLifeViewSet(ModelViewSet):
    queryset = EndOfLife.objects.all()
    serializer_class = EndOfLifeSerializer

class ImpactCategoryViewSet(ModelViewSet):
    queryset = ImpactCategory.objects.all()
    serializer_class = ImpactCategorySerializer

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

class CircularityEnablerViewSet(ModelViewSet):
    queryset = CircularityEnabler.objects.all()
    serializer_class = CircularityEnablerSerializer

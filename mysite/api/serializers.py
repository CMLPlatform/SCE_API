from rest_framework import serializers
from dpp.models import *
from django_countries.serializers import CountryFieldMixin


class DocumentLinkSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields=['file_url']
    
    def get_file_url(self, document: Document):
        request = self.context.get('request')
        file_url = document.file.url
        return request.build_absolute_uri(file_url)

class OrganizationSerializer(CountryFieldMixin, serializers.ModelSerializer):
    legal_documents = DocumentLinkSerializer()
    class Meta:
        model = Organization
        fields = '__all__'

class InstitutionSerializer(OrganizationSerializer):
    class Meta(OrganizationSerializer.Meta):
        model = Institution

class CompanySerializer(OrganizationSerializer):
    class Meta(OrganizationSerializer.Meta):
        model = Company

class ImporterSerializer(CompanySerializer):
    class Meta(CompanySerializer.Meta):
        model = Importer

class ServiceOperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOperator
        fields = ['service_description']

class FacilitySerializer(CountryFieldMixin, serializers.ModelSerializer):
    operator = CompanySerializer(read_only=True)
    class Meta:
        model = Facility
        fields = ['uuid', 'operator', 'country', 'address']

class InstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instruction
        fields = ['label']

class DocumentSerializer(serializers.ModelSerializer):
    issuer = InstitutionSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['file', 'type', 'issuer', 'instructions', 'language', 'issue_date', 'expiry_date', 'file_url']
    
    def get_document_url(self):
        request = self.context.get('request')
        file_url = self.file.url
        return request.build_absolute_uri(file_url)

class ProductPropertiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProperties
        exclude = ['product']

class DppDetailsSerializer(serializers.ModelSerializer):
    compliance_documents = serializers.SerializerMethodField()
    importer = ImporterSerializer()

    class Meta:
        model = DppDetails
        exclude = ['product']
    
    def get_compliance_documents(self, obj):
        doc_dict = {}
        for doc in obj.compliance_documents.all():
            doc_dict.setdefault(doc.type, []).append(doc.file.url)
            #FIXME: could also use DocumentLinkSerializer
        return doc_dict

class EmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emission
        fields = ['name', 'unit']

class ProductExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExchange
        exclude = ['process']

class EnvExchangeSerializer(serializers.ModelSerializer):
    substance = EmissionSerializer(read_only=True)
    class Meta:
        model = EnvExchange
        exclude = ['process']

class ActivitySerializer(serializers.ModelSerializer):
    prod_exchanges = ProductExchangeSerializer()
    env_exchanges = EnvExchangeSerializer()
    class Meta:
        model = Activity
        fields = '__all__'

class ManufacturingProcessSerializer(ActivitySerializer):
    class Meta(ActivitySerializer.Meta):
        model = ManufacturingProcess
        fields = ['name', 'amount', 'facility', 'description', 'modified_at']
        #, 'prod_exchanges', 'env_exchanges']

class BackgroundProcessSerializer(ManufacturingProcessSerializer):
    class Meta(ManufacturingProcessSerializer.Meta):
        model = BackgroundProcess
        fields = ['name', 'amount', 'description', 'modified_at', 'database']

class ProcessSerializer(ActivitySerializer):
    class Meta(ActivitySerializer.Meta):
        model = Process

class ProductionLineSerializer(serializers.ModelSerializer):
    mass_balance = DocumentLinkSerializer()
    energy_balance = DocumentLinkSerializer()
    class Meta:
        model = ProductionLine
        fields = ['name', 'description', 'final_product', 'facility', 'modified_at', 'mass_balance', 'energy_balance']

class AliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alias
        fields = ['product', 'user', 'alt_name']

class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transport
        fields = ['production_line', 'product', 'distance', 'mode']

class MaterialSerializer(CountryFieldMixin, serializers.ModelSerializer):
    is_critical = serializers.BooleanField()

    class Meta:
        model = Material
        exclude = ['density', 'recycled_fraction', 'recyclable_fraction', 'biobased_fraction', 'renewable_fraction']

class HazardousMaterialSerializer(MaterialSerializer):
    safety_instructions = DocumentLinkSerializer()
    class Meta(MaterialSerializer.Meta):
        model = HazardousMaterial

class CompositionSerializer(serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True)
    class Meta:
        model = Composition
        exclude = ['id', 'product']

class ConcentrationSerializer(serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True)
    class Meta:
        model = Concentration
        exclude = ['id', 'product']

class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        exclude = ['id', 'product']

class ItemExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemExchange
        exclude = ['id', 'event']

class LifeCycleEventSerializer(serializers.ModelSerializer):
    item_exchanges = ItemExchangeSerializer(many=True, read_only=True)
    activity_data = ManufacturingProcessSerializer()
    class Meta:
        model = LifeCycleEvent
        exclude = ['product']

class InspectionEventSerializer(LifeCycleEventSerializer):
    diagnostic_results = DocumentLinkSerializer()
    class Meta(LifeCycleEventSerializer.Meta):
        model = InspectionEvent

class MaintenanceEventSerializer(LifeCycleEventSerializer):
    maintenance_plan = DocumentLinkSerializer()
    class Meta(LifeCycleEventSerializer.Meta):
        model = MaintenanceEvent

class DisassemblyEventSerializer(LifeCycleEventSerializer):
    class Meta(LifeCycleEventSerializer.Meta):
        model = DisassemblyEvent

class IndicatorSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndicatorSet
        fields = ['name', 'start_date', 'end_date']

class ImpactCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactCategory
        fields = ['name']

class ImpactIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactIndicator
        fields = ['method', 'description', 'unit', 'is_environmental', 'indicator_set', 'impact_category']

class SustainabilityScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = SustainabilityScore
        exclude = ['id', 'evaluation']

class SustainabilityEvaluationSerializer(serializers.ModelSerializer):
    sustainability_score = SustainabilityScoreSerializer(many=True, read_only=True)
    assessed_by = InstitutionSerializer(read_only=True)

    class Meta:
        model = SustainabilityEvaluation
        exclude = ['id', 'product']

class CircularityIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityIndicator
        fields = ['id', 'name', 'description', 'is_static', 'unit']

class CircularityScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityScore
        fields = ['evaluation', 'indicator', 'value', 'uncertainty', 'comment']

class CircularityEvaluationSerializer(serializers.ModelSerializer):
    circularility_score = CircularityScoreSerializer(many=True, read_only=True)
    report = DocumentLinkSerializer()
    assessed_by = InstitutionSerializer(read_only=True)
    class Meta:
        model = CircularityEvaluation
        exclude = ['id', 'product']

class CircularityTrackerSerializer(CircularityScoreSerializer):
    class Meta(CircularityScoreSerializer.Meta):
        model = CircularityTracker
        fields = ['name', 'description', 'functionality']

class FlowSerializer(serializers.ModelSerializer):
    # Serialize foreign keys (left variable is related_name)
    properties = ProductPropertiesSerializer(read_only=True)
    concentration = ConcentrationSerializer(many=True, read_only=True)
    composed_of = ComponentSerializer(many=True, read_only=True)
    details = DppDetailsSerializer(read_only=True, allow_null=True)
    # sustainability_evaluation = SustainabilityEvaluationSerializer(many=True, allow_null=True)
    # circularity_evaluation = CircularityEvaluationSerializer(many=True, allow_null=True)
    latest_socioecon_evaluation = serializers.SerializerMethodField()
    latest_environmental_evaluation = serializers.SerializerMethodField()
    latest_circularity_evaluation = serializers.SerializerMethodField()
    manufacturing_info = ManufacturingProcessSerializer(allow_null=True)

    class Meta:
        model = Flow
        fields = '__all__'
        depth = 1

    def get_latest_socioecon_evaluation(self, obj):
        latest = obj.sustainability_evaluation.order_by('-assessment_date').first()
        if latest is None:
            return None
        return SustainabilityEvaluationSerializer(latest).data

    def get_latest_environmental_evaluation(self, obj):
        latest = obj.sustainability_evaluation.order_by('-assessment_date').first()
        if latest is None:
            return None
        return SustainabilityEvaluationSerializer(latest).data

    def get_latest_circularity_evaluation(self, obj):
        latest = obj.circularity_evaluation.order_by('-assessment_date').first()
        if latest is None:
            return None
        return CircularityEvaluationSerializer(latest).data

class ProductModelSerializer(FlowSerializer):
    class Meta(FlowSerializer.Meta):
        model = ProductModel

class SecondaryProductSerializer(ProductModelSerializer):
    class Meta(ProductModelSerializer.Meta):
        model = SecondaryProduct

class ProductBatchSerializer(FlowSerializer):
    model = ProductModelSerializer()
    class Meta(FlowSerializer.Meta):
        model = ProductBatch

class ProductItemSerializer(serializers.ModelSerializer):
    product_batch = ProductBatchSerializer(read_only=True)
    service_events = LifeCycleEventSerializer(many=True, read_only=True)
    class Meta:
        model = ProductItem
        fields = '__all__'

class MetadataSerializer(serializers.ModelSerializer):
    issuer = OrganizationSerializer(read_only=True)
    reo = CompanySerializer(read_only=True)
    product_item = ProductItemSerializer()
    class Meta:
        model = Metadata
        fields = '__all__'

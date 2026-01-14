from rest_framework import serializers
from dpp.models import Organization, Institution, Company, Importer, ServiceOperator, Metadata, Instruction, Document, Material, HazardousMaterial, ProductModel, ProductBatch, ProductProperties, DppDetails, SecondaryProduct, Emission, Composition, ProductItem, Activity, ManufacturingProcess, ProductionLine, Process, SharedProcess, BackgroundProcess, ProductExchange, EnvExchange, Alias, Transport, LifeCycleEvent, InspectionEvent, MaintenanceEvent, ItemExchange, DisassemblyEvent, IndicatorSet, ImpactCategory, ImpactIndicator, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityTracker

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['organization_id', 'name', 'address', 'contact_email', 'website', 'legal_documents']

class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ['type']

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['vat_number']

class ImporterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Importer
        fields = ['EORI_number']

class ServiceOperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOperator
        fields = ['service_description']

class MetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metadata
        fields = ['registration_number', 'creation_date', 'last_modified', 'version', 'language', 'access_link', 'access_policy', 'access_log_enabled', 'verification_type', 'credential_format', 'storage_location', 'audit_trail_mechanism', 'update_interval']

class InstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instruction
        fields = ['label']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['file', 'type', 'issuer', 'instructions', 'language', 'issue_date', 'expiry_date']

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ['name', 'density', 'recycled_fraction', 'recyclable_fraction', 'biobased_fraction', 'reused_fraction', 'renewable_fraction', 'criticality_level']

class HazardousMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = HazardousMaterial
        fields = ['CAS_number', 'safety_instructions']

class ProductModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['name', 'unit', 'brand', 'description', 'unit_price', 'taric_code', 'hs_code']

class ProductBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBatch
        fields = ['batch_number', 'model']

class ProductPropertiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductProperties
        fields = ['product', 'weight', 'weight_unit', 'volume', 'volume_unit', 'includes_packaging', 'density']

class DppDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DppDetails
        fields = ['product', 'vendor_or_importer', 'origin', 'CPV_code', 'GS1_GPC_code', 'quality_compliance_documents', 'warranty_period', 'spare_parts_availability_duration', 'takeback_system']

class SecondaryProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondaryProduct
        fields = ['circularity', 'is_waste']

class EmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emission
        fields = ['name', 'unit']

class CompositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Composition
        fields = ['product', 'material', 'quantity', 'unit']

class ProductItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductItem
        fields = ['product_batch', 'DPP_metadata', 'serial_number', 'GTIN_code', 'production_date', 'circularity']

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['name', 'amount', 'operator', 'description']

class ManufacturingProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManufacturingProcess
        fields = ['functional_flow', 'modified_at']

class ProductionLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionLine
        fields = ['name', 'description', 'final_product', 'operator', 'modified_at', 'mass_balance', 'energy_balance']

class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ['production_line', 'functional_flow', 'is_outsourced', 'created_at', 'modified_at']

class SharedProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = SharedProcess
        fields = '__all__'

class BackgroundProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackgroundProcess
        fields = ['created_at', 'database', 'db_code', 'tags', 'type']

class ProductExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExchange
        fields = ['product', 'process', 'type']

class EnvExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvExchange
        fields = ['substance', 'process', 'compartment']

class AliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alias
        fields = ['product', 'user', 'alt_name']

class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transport
        fields = ['production_line', 'product', 'distance', 'mode']

class LifeCycleEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LifeCycleEvent
        fields = ['id', 'product', 'operator', 'event_type', 'date', 'maintenance_plan', 'activity_data']

class InspectionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionEvent
        fields = ['diagnostic_results']

class MaintenanceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceEvent
        fields = ['description', 'affected_functionality', 'software_or_hardware', 'root_cause', 'diagnostics_performed', 'corrective_action']

class ItemExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemExchange
        fields = ['item', 'event', 'amount']

class DisassemblyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisassemblyEvent
        fields = '__all__'

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

class SustainabilityEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SustainabilityEvaluation
        fields = ['product', 'functional_amount', 'system_boundaries', 'geographical_scope', 'temporal_scope', 'impact_assessment_method', 'software_used', 'allocation_method', 'assessment_date', 'assessed_by']

class SustainabilityScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = SustainabilityScore
        fields = ['impact_category', 'evaluation', 'impact_value', 'upstream_phase', 'manufacturing_phase', 'use_phase', 'end_of_life_phase', 'scope_1_2_3']

class CircularityEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityEvaluation
        fields = ['product', 'assessment_date', 'assessed_by', 'report']

class CircularityIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityIndicator
        fields = ['id', 'name', 'description', 'is_static', 'unit']

class CircularityScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityScore
        fields = ['evaluation', 'indicator', 'value', 'modified_at', 'uncertainty', 'comment']

class CircularityTrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularityTracker
        fields = ['type', 'description']

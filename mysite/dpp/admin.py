from django.contrib import admin
from .models import Institution, Company, Importer, ServiceOperator, Metadata, Instruction, Document, Material, HazardousMaterial, CriticalRawMaterial, ProductType, Packaging, SecondaryProduct, Emission, Composition, ProductItem, ProductionLine, Activity, Process, SharedProcess, ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo, ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityEnabler, CircularityTracker

# Models that can be modified by admin:
admin.site.register(Company)
admin.site.register(Importer)
admin.site.register(Activity)
admin.site.register(Process)
admin.site.register(ProductionLine)
admin.site.register(ProductType)
admin.site.register(ProductExchange)
admin.site.register(EnvExchange)
admin.site.register(Instruction)
admin.site.register(Emission)
admin.site.register(ImpactCategory)
admin.site.register(CircularityIndicator)

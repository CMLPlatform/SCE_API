from django.contrib import admin
from .models import Institution, Company, Importer, ServiceOperator, Metadata, Instruction, Document, Material, HazardousMaterial, CriticalRawMaterial, ProductType, Packaging, SecondaryProduct, Emission, Composition, Product, ProductionLine, Process, SharedProcess, ProductExchange, EnvExchange, BillOfMaterials, PackagingInfo, ServiceEvent, ServiceRecord, ReplacedComponents, EndOfLife, ImpactCategory, SustainablityEvaluation, SustainabilityScore, CircularityEvaluation, OldCircularityIndicator, CircularityIndicator, CircularityScore, CircularityEnabler, CircularityTracker

# Models that can be modified by admin:
admin.site.register(Company)
admin.site.register(Importer)
admin.site.register(Process)
admin.site.register(ProductionLine)
admin.site.register(ProductType)
admin.site.register(ProductExchange)


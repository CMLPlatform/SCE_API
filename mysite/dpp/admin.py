from django.contrib import admin
from .models import Institution, Company, Importer, ServiceOperator, Metadata, Instruction, Document, Material, HazardousMaterial, ProductBatch, DppDetails, SecondaryProduct, Emission, Composition, ProductItem, ProductionLine, Activity, Process, SharedProcess, ProductExchange, EnvExchange, ServiceEvent, ServiceRecord, ReplacedComponent, EndOfLife, ImpactCategory, SustainabilityEvaluation, SustainabilityScore, CircularityEvaluation, CircularityIndicator, CircularityScore, CircularityEnabler, CircularityTracker

# Models that can be modified by admin:
admin.site.register(Company)
admin.site.register(Document)
admin.site.register(Importer)
admin.site.register(Activity)
admin.site.register(Process)
admin.site.register(ProductionLine)
admin.site.register(ProductBatch)
admin.site.register(Composition)
admin.site.register(DppDetails)
admin.site.register(ProductExchange)
admin.site.register(EnvExchange)
admin.site.register(Instruction)
admin.site.register(Emission)
admin.site.register(ImpactCategory)
admin.site.register(CircularityIndicator)

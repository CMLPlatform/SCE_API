from django.contrib import admin
from .models import *

# Models that can be modified by admin:
admin.site.register(Company)
admin.site.register(Importer)
admin.site.register(Facility)
admin.site.register(Activity)
admin.site.register(ManufacturingProcess)
admin.site.register(BackgroundProcess)
admin.site.register(Process)
admin.site.register(ProductionLine)
admin.site.register(Flow)
admin.site.register(ProductModel)
admin.site.register(Composition)
admin.site.register(DppDetails)
admin.site.register(ProductExchange)
admin.site.register(EnvExchange)
admin.site.register(Instruction)
admin.site.register(Emission)
admin.site.register(ImpactCategory)
admin.site.register(CircularityIndicator)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'get_instructions']
    filter_horizontal = ('instructions',)
    list_filter = ['instructions']
    search_fields = ['file']

    def get_instructions(self, obj):
        return ", ".join(label.name for label in obj.instructions.all())
    get_instructions.short_description = 'Instructions'
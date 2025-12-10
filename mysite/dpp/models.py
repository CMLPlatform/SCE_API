from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django_countries.fields import CountryField
import datetime

FRACTION_VALIDATOR = [MinValueValidator(0), MaxValueValidator(1)]

## Organizations and companies

class Organization(models.Model):
    organization_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.TextField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    legal_documents = models.ForeignKey('Document', blank=True, null=True, on_delete=models.SET_NULL, related_name='organization_legal_documents', help_text="Add official legal documentation associated with the company. This may include licenses, registration papers, permits, or other legally mandated certificates.")

    # class Meta:  # If made abstract, cannot link legal_documents here
    #     abstract = True

    def __str__(self):
        return self.name

class Institution(Organization):
    type = models.CharField(max_length=30, choices={'university': 'University', 'research': 'Research institute', 'governmental': 'Government agency', 'ngo': 'Non-governmental organization', 'statistical': 'Statistical office', 'accountant': 'Accountant office', 'legal': 'Legal institution', 'other': 'Other'})

class Company(Organization):
    vat_number = models.CharField("VAT number", max_length=50, blank=True)
    country = CountryField()  #NOTE: address inherited from Organization

    class Meta:
        verbose_name_plural = "Companies"

class Importer(Company):  #FIXME: rename to vendor/dealer
    EORI_number = models.CharField(max_length=100, blank=True)

class ServiceOperator(Company):
    service_description = models.CharField(max_length=100)

def get_unknown_company():
    unknown, created = Company.objects.get_or_create(name="Unknown company")
    return unknown

def get_unknown_importer():
    unknown, created = Importer.objects.get_or_create(name="Unknown importer")
    return unknown

def get_unknown_servicer():
    unknown, created = ServiceOperator.objects.get_or_create(
        name="Unknown service operator",
        service_description="Deleted service",
        )
    return unknown

class Metadata(models.Model):  #FIXME: Should each product have unique metadata?
    registration_number = models.UUIDField(primary_key=True, editable=False)
    issuer = models.ForeignKey(Company, verbose_name="Responsible Economic Operator", on_delete=models.PROTECT)
    creation_date = models.DateField(auto_now_add=True)
    last_modified = models.DateField(auto_now=True)
    version = models.CharField(max_length=20)
    # Data access & governance
    access_link = models.URLField(max_length=200, blank=True, help_text="URL to full DPP record.")
    access_policy = models.URLField(max_length=200, blank=True, help_text="URL to data access terms and conditions.")
    access_log_enabled = models.BooleanField(default=True)
    verification_type = models.SmallIntegerField(choices={0: 'None', 1: 'Digital signature', 2: 'Third party', 3: 'Blockchain'}, default=0)
    credential_format = models.CharField(max_length=50, choices={'json_ld': 'JSON-LD', 'verifialble':'Verifiable credential', 'xml': 'XML', 'other': 'Other'})
    storage_location = models.SmallIntegerField(choices={0: 'Undeclared', 1: 'On-premise server', 2: 'Commercial cloud server', 3: 'Centralized certified server', 4: 'Decentralized storage'}, default=0)
    audit_trail_mechanism = models.SmallIntegerField(choices={0: 'None', 1: 'Log files', 2: 'Immutable ledger'}, default=0)
    update_interval = models.CharField(max_length=2, choices={'-': 'never', 'W': 'weekly', 'M': 'monthly', 'Q': 'quarterly', 'A': 'annually', 'E': 'event_driven'}, default='-')

    class Meta:
        verbose_name_plural = "Metadata"

    def __str__(self):
        return f"DPP #{self.registration_number} issued by {self.issuer.name}"

## Documents

INSTRUCTION_TYPES = {
    'installation': 'Installation / assembly',
    'use': 'Use',
    'repair': 'Repair',
    'maintenance': 'Maintenance',
    'refurbishment': 'Refurbishment',
    'disassembly': 'Disassembly',
    'disposal': 'Disposal',
}

class Instruction(models.Model):
    label = models.CharField(max_length=20, primary_key=True, choices=INSTRUCTION_TYPES, unique=True)

    def __str__(self):
        return self.get_label_display()

class Document(models.Model):  #TODO: security check on files
    DOCUMENT_TYPES = {
        "Technical document":
            [
                ("technical_drawing", "Technical drawing"),
                ("safety_sheet", "Safety sheet"),
                ("conformity_certificate", "Conformity certificate"),
                ("mass_balance", "Mass balance"),
                ("energy_balance", "Energy balance"),
                ("other", "Other"),
            ],
        "Compliance document":
        {'compliance': 'Compliance report', 'quality_cert': 'Quality certificate', 'safety_data': 'Safety data sheet', 'legal': 'Legal document', 'labor': 'Labor compliance', 'qms': 'Quality Management System certificate', 'warranty': 'Warranty information', 'spare_parts': 'Spare parts availability', 'takeback': 'Return and take-back'},
        "Manuals":
        {'manual': 'User manual', 'maintenance': 'Maintenance manual', 'installation': 'Installation guide', 'eol': 'End-of-life guidelines', 'datasheet': 'Product data sheet'},
        "Labels":
        {'label': 'Voluntary label', 'energy_label': 'Energy label', 'ecolabel': 'Ecolabel', 'recycling_label': 'Recycling label', 'legal': 'Legal markings'},
    }

    file = models.FileField(upload_to='documents/')
    type = models.CharField(
        "Document type", max_length=25, choices=DOCUMENT_TYPES
    )
    instructions = models.ManyToManyField(Instruction, blank=True, help_text="Select all that apply. Instructions included in this document (ony for manauals)")
    language = models.CharField(max_length=40, blank=True)
    # file_type = models.CharField(max_length=5, default=file.split('.')[-1])
    upload_date = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Validate that instructions are only set for manuals
        if self.type in self.DOCUMENT_TYPES['Manuals']:
            if not self.instructions.exists():
                raise ValidationError({
                    "instructions": "A manual must have at least one instruction type."
                })
        elif self.instructions.exists():
            raise ValidationError({"instructions": "Instructions can only be associated with manuals."})
    
    def save(self, *args, **kwargs):
        # Save instance first so M2M relations are available
        super().save(*args, **kwargs)

        manuals = self.DOCUMENT_TYPES['Manuals']

        # If there are instructions but this is not a manual, raise validation error
        if self.instructions.exists() and self.type not in manuals:
            raise ValidationError({"instructions": "Instructions can only be associated with manuals."})

        # If this is a manual but no instructions have been attached, raise validation error
        if self.type in manuals and not self.instructions.exists():
            raise ValidationError({"instructions": "A manual must have at least one instruction type."})

    def __str__(self):
        return self.file.name.split('/')[-1]
    @property
    def filename(self):
        return self.file.name.split('/')[-1]

# class ComplianceDocument(Document):
#     super.type = models.CharField(choices=DOCUMENT_TYPES['Compliance document'])

# class Manual(Document):
#     language = models.CharField(max_length=40)
#     type = models.CharField(default='manual', max_length=20, choices={'manual': 'User manual', 'circularity': 'Circularity manual', 'maintenance': 'Maintenance manual', 'installation': 'Installation guide', 'eol': 'End-of-life guidelines', 'datasheet': 'Product data sheet'})

# class Labels(Document):
#     type = models.CharField(max_length=20, default='label', choices={'label': 'Voluntary label', 'energy_label': 'Energy label', 'ecolabel': 'Ecolabel', 'recycling_label': 'Recycling label', 'legal': 'Legal markings'})


## Technosphere: products and processes

class Material(models.Model):
    name = models.CharField("Material name", max_length=50)
    density = models.FloatField(blank=True, default=0)
    recycled_content = models.FloatField("Recycled content (%)", default=0, validators=FRACTION_VALIDATOR)
    recyclable_percentage = models.FloatField("Recyclable material (%)", default=0, validators=FRACTION_VALIDATOR)
    biobased_percentage = models.FloatField("Bio-based material (%)", default=0, validators=FRACTION_VALIDATOR)
    reused_fraction = models.FloatField("Reused material (%)", default=0, validators=FRACTION_VALIDATOR)
    renewable_fraction = models.FloatField("Sustainable and renewable material (%)", default=0, validators=FRACTION_VALIDATOR)

    def __str__(self):
        return self.name

class HazardousMaterial(Material):
    CAS_number = models.CharField(max_length=50, blank=True, unique=True)
    safety_instructions = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='material_safety_instructions')  # (SafetyDataSheet)
    substance_concentration = models.FloatField(blank=True, default=1, validators=FRACTION_VALIDATOR)  #TODO: set this attribute on products
    concentration_unit = models.CharField(max_length=20, choices={'wt': 'Weight fraction'})
    substance_location = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='material_location')  # (TechnicalDrawings)

class CriticalRawMaterial(Material):
    supply_risk_level = models.CharField(max_length=10)
    substance_concentration = models.FloatField()
    concentration_unit = models.CharField(max_length=20)

class ProductModel(models.Model):
    UNIT_CHOICES = {
        'pcs': 'pieces',
        'Mass': {
            'kg': 'kg',
            'g': 'g',
            'lb': 'lb',
            'oz': 'oz',
        },
        'Volume': {
            'l': 'liters',
            'cm3': 'cm3',
            'dm3': 'dm3',
            'm3': 'm3 (cubic meters)',
            'ft3': 'ft3 (cubic feet)',
        },
        'Energy': {
            'kWh': 'kWh',
            'MWh': 'MWh',
            'MJ': 'MJ',
            'GJ': 'GJ',
        }
    }
    name = models.CharField("Model or product name", max_length=100)
    unit = models.CharField(max_length=15, default='pcs', help_text="How the product is counted, e.g. pcs, bottles, sheets, kWh")
    description = models.TextField(max_length=200, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    weight = models.FloatField("Weight of 1 unit", blank=True, null=True, default=1, validators=[MinValueValidator(0)])
    weight_unit = models.CharField(max_length=2, choices=UNIT_CHOICES['Mass'], default='kg')
    volume = models.FloatField(validators=[MinValueValidator(0)])
    volume_unit = models.CharField(max_length=3, choices=UNIT_CHOICES['Volume'], default='m3')

    taric_code = models.CharField(max_length=20, blank=True, help_text="TARIC (customs code)")
    hs_code = models.CharField("HS code", max_length=10, blank=True, help_text="Harmonized System classification (customs code)")

    def __str__(self):
        return self.name
    
    @property
    def producer_of(self):
        """Get the manufacturer of this product
        (operator from the Process that produces this ProductModel).
        """
        process = Process.objects.filter(output_product=self).first()
        return process.operator if process else None

class ProductBatch(ProductModel):
    batch_number = models.IntegerField(blank=True, null=True)
    
class DppProduct(ProductBatch):
    """A product for which a Digital Product Passport (DPP) is issued.
    Typically a final product sold in stores.
    """
    vendor_or_importer = models.ForeignKey(Importer, blank=True, null=True, on_delete=models.SET(get_unknown_importer), related_name='sold_products')
    origin = models.ForeignKey(Company, on_delete=models.SET(get_unknown_company), related_name="manufactured_products") # duplicate of ProductionLine.operator

    # Documents and other quality compliance info
    quality_compliance_documents = models.ManyToManyField(Document, blank=True)
    warranty_period = models.DecimalField(default=0, max_digits=3, decimal_places=1, validators=[MinValueValidator(0)], help_text="Warranty period in years")
    spare_parts_availability_duration = models.DecimalField(default=0, max_digits=3, decimal_places=1, validators=[MinValueValidator(0)], help_text="Spare parts availability in years")
    takeback_system = models.CharField(max_length=10, choices={'no': 'No take-back system', 'basic': 'Collection on request', 'active': 'Structured take-back with dedicated channels or collection points', 'advanced': 'Certified, traceable take-back system'}, default='no')
    # technical_drawings = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='product_drawings')
    # conformity_certificate = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='product_conformity_certificate')


class Packaging(ProductBatch):
    pass

class SecondaryProduct(ProductModel):
    CIRCULARITY_CHOICES = {
        'R3': 'reused',
        'R5': 'refurbished',
        'R6': 'remanufactured',
        'R7': 'repurposed',
        'R8': 'recycled',
        'in': 'incinerated',
        'lf': 'landfilled',
        '-': 'unknown',
    }
    circularity = models.CharField(max_length=2, choices=CIRCULARITY_CHOICES, default='-')
    is_waste = models.BooleanField(default=False)

class Emission(models.Model):
    name = models.CharField(max_length=50)
    unit = models.CharField(max_length=10, default='g')

    def __str__(self):
        return self.name

class Composition(models.Model):
    product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE, related_name='composition')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='used_in')
    quantity = models.FloatField(help_text="The amount of material present in product.")
    # fraction = models.FloatField(validators=FRACTION_VALIDATOR)

    origin_country = CountryField(blank=True, null=True, help_text="Only fill for Critical Raw Materials")

    class Meta:
        unique_together = ('product', 'material')
        ordering = ['product', 'material']

    def clean(self):
        if isinstance(self.material, CriticalRawMaterial):
            if not self.origin_country:
                raise ValidationError({
                    'origin_country': 'Origin country is mandatory when the material is a Critical Raw Material.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()   # Enforce clean() on every save
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.amount}% {self.material} in ({self.product})"

class ProductItem(models.Model):  # =ProductInformation in DPP
    verbose_plural_name = "Products"
    product_batch = models.ForeignKey(ProductBatch, on_delete=models.PROTECT)
    DPP_metadata = models.ForeignKey(Metadata, on_delete=models.PROTECT, blank=True)
    serial_number = models.CharField(max_length=50, unique=True)  #FIXME: make only the combination of product and manufacturer unique?
    CPV_code = models.CharField(max_length=20, blank=True, help_text="Common Procurement Vocabulary code")
    GS1_GPC_code = models.CharField(max_length=20, blank=True, help_text="Global Product Classification code")
    GTIN_code = models.CharField(max_length=20, help_text="Global Trade Item Number (or comparable)")
    production_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return f"Product #{self.name}"


class Activity(models.Model):  #TODO: check what common fields can be moved here
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Activities"

    def __str__(self):
        return self.name

class ProductionLine(Activity):
    description = models.TextField(max_length=300, blank=True)
    final_product = models.OneToOneField(ProductBatch, on_delete=models.RESTRICT, verbose_name="Final product", help_text="The output product of this production line")
    operator = models.ForeignKey(Company, verbose_name="Producing company", blank=True, null=True, on_delete=models.SET(get_unknown_company))
    modified_at = models.DateField(auto_now=True)
    mass_balance = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='mass_balance', help_text="Add a document showing all material flows going in and out of the production line. (Optional)")
    energy_balance = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='energy_balance', help_text="Add a document showing all energy flows going in and out of the production line. (Optional)")

    def __str__(self):
        return self.name
    
    def check_unused_outputs(self):
        """
        Check which Process functional_flows are not linked to another Process.
        Return a message if unused outputs differ from the final_product.
        """
        process_list = self.process_set.all().order_by('order')
        final_product = self.final_product
        unused_outputs = []
        
        for process in process_list:
            # Check if this process's output is used as input in any Exchange
            is_linked = ProductExchange.objects.filter(
                product=process.functional_flow,
                process__production_line=self
            ).exists()
            
            if not is_linked:
                unused_outputs.append(process.functional_flow)
        
        # Check if any unused output differs from final_product
        unexpected_unused = [
            product for product in unused_outputs 
            if product != final_product
        ]
        
        if unexpected_unused:
            product_names = ', '.join([p.name for p in unexpected_unused])
            return f"Warning: Products [{product_names}] are not linked to other processes."
        
        return ""  # All good

class Process(Activity):
    production_line = models.ForeignKey(ProductionLine, on_delete=models.CASCADE)  # Assuming 1:M
    functional_flow = models.ForeignKey(ProductBatch, blank=True, null=True, on_delete=models.SET_NULL, verbose_name="Main output", related_name='produced_by')  #FIXME: make this 1:1?
    amount = models.FloatField(default=1, help_text="Number of units produced")
    # energy_use = models.FloatField()
    is_outsourced = models.BooleanField("Outsourced", default=False)
    operator = models.ForeignKey(Company, blank=True, null=True, on_delete=models.CASCADE)
    location = CountryField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.functional_flow:
            raise ValidationError("functional_flow cannot be blank. Please select a product.")

    def save(self, *args, **kwargs):
        # If operator is not set, default to production line operator
        if self.production_line and not self.operator:
            self.operator = self.production_line.operator
        if not self.location:
            self.location = self.operator.country
        self.clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Processes"

    def __str__(self):
        return self.name

class SharedProcess(Process):
    """ Represents a process that is shared across multiple processes or production lines.
    functional_flow defaults to the final product of the production line.
    """
    class Meta:
        proxy = True
        verbose_name = "Auxiliary process"
        verbose_name_plural = "Auxiliary processes"

    def save(self, *args, **kwargs):
        # If functional flow is not set, default to the final product of production line
        if self.production_line and not self.functional_flow:
            self.functional_flow = self.production_line.final_product
        super().save(*args, **kwargs)

class BackgroundProcess(Activity):
    functional_flow = models.ForeignKey(ProductModel, blank=True, null=True, on_delete=models.SET_NULL, verbose_name="Main product", related_name='produced_by_other')
    location = CountryField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    database = models.CharField(max_length=50, blank=True)
    #TODO: more UnitProcess attributes

    class Meta:
        verbose_name = "Average market process"
        verbose_name_plural = "Average market processes"

class Exchange(models.Model):
    """ Represents the input to or output of a Process."""
    UNCERTAINTY_TYPES = {
        'none': 'No uncertainty',
        'na': 'Not available',
        'interval': 'Interval (min-max)',
        'normal': 'Normal distribution',
        'lognormal istribution': 'Lognormal distribution',
        'triangular': 'Triangular distribution',
    }
    amount = models.FloatField()
    direction = models.CharField(max_length=3, choices={'in': 'Input', 'out': 'Output', 'ff': 'functional flow'})  #NOTE: out means waste
    is_proxy = models.BooleanField("This is an approximation of the actual product", default=False)
    observed = models.BooleanField("Quantity is", choices={True: "Measured", False: "Modeled or calculated"}, default=False)
    uncertainty_type = models.CharField(max_length=30, choices=UNCERTAINTY_TYPES, default='none', help_text="If the amount is uncertain, how can this uncertainty be described?")
    loc = models.FloatField("Mean or median", blank=True, null=True)
    scale = models.FloatField("Standard deviation", blank=True, null=True)  # or geometric stddev
    shape = models.FloatField(blank=True, null=True, help_text="for lognormal distribution")
    minimum = models.FloatField(blank=True, null=True, help_text="for interval and triangular distribution")
    maximum = models.FloatField(blank=True, null=True, help_text="for interval and triangular distribution")
    # unit = models.CharField(max_length=20) #product.unit
    # description = models.TextField(max_length=300, blank=True)

    class Meta:
        abstract = True

class ProductExchange(Exchange):
    """Represents the input or output of a product by an activity."""
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name='exchanged_by')
    process = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='prod_exchanges')

    class Meta:
        unique_together = ['product', 'process', 'direction']
        ordering = ['process', 'product']

    def __str__(self):
        return f"{self.direction}: {self.amount} {self.product.unit} {self.product}"

class EnvExchange(Exchange):
    """Represents an emission or resource extraction by a process."""
    COMPARTMENTS = {
        'air': 'air',
        'soil': 'soil',
        'groundwater': 'groundwater',
        'seawater': 'seawater',
        'surface_water': 'surface water',
    }
    substance = models.ForeignKey(Emission, on_delete=models.CASCADE, related_name='exchanges')
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='env_exchanges')
    compartment = models.CharField(max_length=20, choices=COMPARTMENTS)

    class Meta:
        unique_together = ['substance', 'compartment', 'direction']
        ordering = ['process', 'substance']
        verbose_name = 'Emission or Extraction'
        verbose_name_plural = 'Emissions & Extractions'

    def __str__(self):
        return f"{self.direction}: {self.amount} {self.substance.unit} {self.substance}"

class BillOfMaterials(models.Model):
    """ Represents the components contained in a ProductBatch."""
    product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE, related_name='bom')  # product or subclass Material
    component = models.ForeignKey(ProductBatch, on_delete=models.CASCADE, related_name='part_of')  #FIXME: could also contain Material
    amount = models.FloatField()
    unit = models.CharField(max_length=20, choices=ProductModel.UNIT_CHOICES) # Choices validated below

    @property  # Dynamic choices of units based on product type
    def find_units(self):
        if self.component.product_type.unit == 'pcs':
            return ['pcs']
        else:
            return ProductModel.UNIT_CHOICES['Mass'].keys() | ProductModel.UNIT_CHOICES['Volume'].keys()

    def clean(self):
        if self.product == self.component:
            raise ValidationError("A product cannot contain itself as a component.")
        if self.unit and self.unit not in self.find_units():
            raise ValidationError(f"Invalid unit '{self.unit}'. Allowed: {', '.join(self.find_units())}.")

    class Meta:
        verbose_name_plural = "Bills of Materials"
        unique_together = ('product', 'component')
        ordering = ['product', 'component']

    def __str__(self):
        return f"{self.amount} {self.unit} {self.component} in ({self.product})"

class PackagingInfo(models.Model):
    product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE, related_name='packaging_info')
    packaging = models.ForeignKey(Packaging, on_delete=models.CASCADE, related_name='used_as_packaging')
    packaging_ratio = models.FloatField()

    def __str__(self):
        return f"{self.product} packaged in {self.packaging}"

class Alias(models.Model):
    """Allow companies to define an alternative product name to display"""
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name='alias')
    user = models.ForeignKey(Company, on_delete=models.CASCADE)
    alt_name = models.CharField("Display name", max_length=100)

    class Meta:
        verbose_name_plural = "Aliases"

    def __str__(self):
        return f"{self.product.name} = {self.alt_name}"


## Service and maintenance records

class ServiceEvent(models.Model):
    LIFE_STAGES = {
        'upstream': 'Upstream',
        'manufacturing': 'Manufacturing stage',
        'use': 'Use phase',
        'eol': 'End-of-life stage',
    }
    SERVICE_TYPES = {
        'preventive_maintenance': 'Preventive maintenance',
        'corrective_maintenance': 'Corrective maintenance',
        'modification': 'Modification',
        'upgrade': 'Upgrade',
        'eol': 'End-of-life treatment',
    }
    id = models.UUIDField(primary_key=True, editable=False)
    product = models.ForeignKey(ProductItem, on_delete=models.CASCADE, related_name='service_events')
    operator = models.ForeignKey(ServiceOperator, on_delete=models.CASCADE)
    # life_stage = models.CharField(max_length=20, choices=LIFE_STAGES) # Obsolete, already implied by service_type
    service_type = models.CharField(max_length=30, blank=True, choices=SERVICE_TYPES)
    date = models.DateField(auto_now_add=True)
    maintenance_plan = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL)

    def clean(self):
        if self.service_type in ['preventive_maintenance', 'corrective_maintenance'] and not self.maintenance_plan:
            raise ValidationError("Maintenance plan must be attached for maintenance services.")

class ServiceRecord(models.Model):
    description = models.TextField(max_length=300)
    service_event = models.ForeignKey(ServiceEvent, on_delete=models.CASCADE)
    # Modifications fields
    MODIFICATIONS = {
        'corrective': 'Repair',
        'software': 'Software update',
        'performance': 'Performance upgrade',
        'safety': 'Safety improvement',
        'energy_optimization': 'Energy optimization',
        'compliance': 'Compliance update',
        'other': 'Other',
    }
    modification_category = models.CharField(max_length=50, choices=MODIFICATIONS)
    affected_functionality = models.CharField(max_length=500, blank=True)
    software_or_hardware = models.BooleanField(choices={True: "Software", False: "Hardware"})

    # Repair fields (aka corrective maintenance)
    root_cause = models.TextField(max_length=300, blank=True)
    diagnostics_performed = models.TextField(max_length=300, blank=True)
    corrective_action = models.TextField(max_length=300, blank=True)

class ReplacedComponent(models.Model):
    """ Components that were replaced or added during a service event."""
    service_record = models.ForeignKey(ServiceRecord, on_delete=models.CASCADE, related_name='replaced_components')
    old_component = models.ForeignKey(ProductItem, blank=True, null=True, on_delete=models.SET_NULL, related_name='replaced')
    new_component = models.ForeignKey(ProductItem, on_delete=models.CASCADE, related_name='installed')

    def __str__(self):
        return self.new_component.name

class EndOfLife(models.Model):
    service_record = models.ForeignKey(ServiceRecord, on_delete=models.CASCADE, related_name='end_of_life')
    EOL_TREATMENTS = {
        'recycling': 'Recycling',
        'disposal': 'Disposal',
        'incineration': 'Incineration',
        'stockpiling': 'Stockpiling',
    }
    treatment_type = models.CharField(max_length=20, choices=EOL_TREATMENTS)
    affected_component = models.ForeignKey(ProductItem, on_delete=models.RESTRICT)


## Sustainability evaluation

class IndicatorSet(models.Model):
    """A methodology or group of related impact indicators (e.g. EF3.0)"""
    name = models.CharField(max_length=50)
    start_date = models.DateField("Release date")
    end_date = models.DateField("Phase-out date", blank=True, null=True)

    def __str__(self):
        return self.name

class ImpactCategory(models.Model):
    """The type of impact that is assessed"""
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "Impact categories"

    def __str__(self):
        return self.name

class ImpactIndicator(models.Model):
    """Life Cycle Impact Assessment Method"""
    method = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=40)
    is_environmental = models.BooleanField("Type of impact", choices={True: "Environmental", False: "Socioeconomic"}, default=True)
    indicator_set = models.ForeignKey(IndicatorSet, on_delete=models.SET_NULL, blank=True, null=True)
    impact_category = models.ForeignKey(ImpactCategory, on_delete=models.PROTECT)

    def __str__(self):
        return self.method

class SustainabilityEvaluation(models.Model):  # including metadata
    """
    A sustainability evaluation is defined by a scope definition,
    a functional unit (the final product of a production line), and its amount. 
    """
    # FIXME: perhaps this should also have a field is_environmental, to avoid mismatches in SustainabilityScore
    GEO_CHOICES = {
        'EU': 'European Union (EU)',
        'c': 'Country-specific',
        'glo': 'Global',
        '-': 'Other',
    }
    def get_year():
        return datetime.date.today().year
    
    product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)
    functional_amount = models.FloatField()
    system_boundaries = models.CharField(max_length=200, blank=True)
    geographical_scope = models.CharField(max_length=4, choices=GEO_CHOICES, blank=True)
    temporal_scope = models.CharField(max_length=50, default=str(get_year))
    impact_assessment_method = models.CharField(max_length=50, blank=True, help_text="Specify the environmental impact assessment method. E.g. EF 3.0, ReCiPe, ILCD, TRACI.")
    software_used = models.CharField(max_length=50, blank=True, help_text="Indicate the assessment software used. E.g. OpenLCA, GaBi, SimaPro, Umberto.")
    allocation_method = models.CharField(max_length=6, blank=True, choices={'mass': 'Mass-based', 'econom': 'Economic (price-based)', 'energy': 'Energy-based', 'other': 'Other'}, help_text="How are impacts allocated for co-production processes?")
    assessment_date = models.DateField(default=datetime.date.today)
    assessed_by = models.ForeignKey(Institution, blank=True, null=True, on_delete=models.PROTECT)

    @property
    def reference_flow(self):
        return self.product.name
    @property
    def functional_unit(self):  # literally the unit
        return self.product.unit
    
    def __str__(self):
        return f"Sustainability evaluation of {self.functional_amount} {self.functional_unit} {self.reference_flow}"

class SustainabilityScore(models.Model):
    """
    The indicator results for one impact category in a SustainabilityEvaluation,
    plus contribution analysis data.
    """
    impact_category = models.ForeignKey(ImpactIndicator, on_delete=models.CASCADE)
    evaluation = models.ForeignKey(SustainabilityEvaluation, on_delete=models.CASCADE)
    impact_value = models.FloatField()  # cradle-to-gate total (unit = impact_category.unit)
    upstream_phase = models.FloatField(default=0, validators=FRACTION_VALIDATOR)
    manufacturing_phase = models.FloatField(default=0, validators=FRACTION_VALIDATOR)
    use_phase = models.FloatField(default=0, validators=FRACTION_VALIDATOR)
    end_of_life_phase = models.FloatField(default=0, validators=FRACTION_VALIDATOR)
    scope_1_2_3 = models.FloatField("Scope 1+2+3 CO<sub>2</sub> emission", help_text="Total greenhouse gas emissions associated with the product over its lifecycle, expressed as kg CO<sub>2</sub> equivalents.")

    def __str__(self):
        return f"{self.impact_value} {self.impact_category.unit} for {self.evaluation}"


## Circularity indicators

class CircularityEvaluation(models.Model):
    """A circularity evaluation of a certain ProductBatch."""
    product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)
    assessment_date = models.DateField(default=datetime.date.today, help_text="When the assessment was made or updated.")
    assessed_by = models.ForeignKey(Institution, blank=True, null=True, on_delete=models.PROTECT)
    report = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='circularity_reports', help_text="Report describing the circularity assessment, and manual for monitoring and updating the circularity metrics.")

class CircularityIndicator(models.Model):
    """
    An indicator for measuring circularity performance,
    including description and unit.
    """
    id = models.CharField(max_length=6, primary_key=True)
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=300, blank=True)
    is_static = models.BooleanField(choices={True: "Static", False: "Dynamic"},
                                    default=True)
    unit = models.CharField(max_length=20)

    def __str__(self):
        return self.name

class CircularityScore(models.Model):
    evaluation = models.ForeignKey(CircularityEvaluation, on_delete=models.CASCADE)
    indicator = models.ForeignKey(CircularityIndicator, on_delete=models.CASCADE)
    value = models.FloatField()  #FIXME: validation depends on indicator.unit
    modified_at = models.DateField(auto_now_add=True)
    uncertainty = models.CharField(max_length=100, blank=True)
    comment = models.TextField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.indicator.name}: {self.value}"

#FIXME: a service event should not update the CircularityScore of a Product,
# but rather trigger an updated assessment of the ProductBatch.
# class CircularityUpdate(CircularityScore):
#     service_event = models.ForeignKey(ServiceEvent, on_delete=models.SET_NULL, blank=True, null=True)
#     previous_value = models.FloatField()
    
#     # Change verbose name of 'comment' field
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         comm = self._meta.get_field('comment')
#         comm.verbose_name = 'Change reason'


class CircularityEnabler(CircularityScore):
    ENABLERS = {
        'design': 'Design for circularity',
        'business_model': 'Circular business model',
        'process': 'Circular process or technology',
        'other': 'Other enabler',
    }
    type = models.CharField(max_length=20, choices=ENABLERS)
    description = models.TextField(max_length=300, blank=True, help_text="Description and functionality")

# Alternative interpretation & implementation
class CircularityTracker(CircularityScore):
    name = models.CharField(max_length=50, help_text="The type of traceability system or device in the product")
    description = models.TextField(max_length=200, blank=True, help_text="A short description of the device or system")
    functionality = models.TextField(max_length=200, blank=True, help_text="A short description of the intended functionality")

    def __init__(self, *args, **kwargs):
        # Change verbose name and help text of 'value' field
        quantity = self._meta.get_field('value')
        quantity.verbose_name = 'Quantity'
        quantity.help_text = "Number of such devices or systems in the product"
        super().__init__(*args, **kwargs)


# ## Quality and compliance

# class QualityCompliance(models.Model):
#     product = models.ForeignKey(ProductBatch, on_delete=models.CASCADE)
#     document = models.ForeignKey(Document, on_delete=models.CASCADE)

#     class Meta:
#         unique_together = ('product', 'document')
#         ordering = ['product', 'document']
    
#     def __str__(self):
#         return f"{self.document} linked to {self.product}"

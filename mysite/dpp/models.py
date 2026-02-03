from collections import defaultdict
from django.db import models, transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django_countries.fields import CountryField
import datetime
from uuid import uuid4

FRACTION_VALIDATOR = [MinValueValidator(0), MaxValueValidator(1)]

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
        'gal': 'gallons'
    },
    'Energy': {
        'kWh': 'kWh',
        'MWh': 'MWh',
        'MJ': 'MJ',
        'GJ': 'GJ',
    },
    'Transport': {
        'tkm': 'ton.km',
        'm3km': 'm3.km',
    }
}
CONVERSIONS = {
    'kg': 1,
    'g': 0.001,
    'lb': 0.4535924,
    'oz': 0.02834952,
    'l': 1,
    'cm3': 0.001,
    'dm3': 1,
    'm3': 1000,
    'ft3': 28.3168466,
    'gal': 3.785412,
    'kWh': 1,
    'MWh': 1000,
    'MJ': 1 / 3.6,
    'GJ': 1000 / 3.6,
}

## Organizations and companies

class Organization(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid4, editable=False) # Using default id for simplicity
    name = models.CharField(max_length=100)
    address = models.TextField(max_length=100, blank=True, help_text="Location of the headquarters, or correspondence address")
    country = CountryField()
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

    class Meta:
        verbose_name_plural = "Companies"

class Importer(Company):
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

class Facility(models.Model):
    """
    Describes a manufacturing facility, 
    i.e. a place where production takes place.
    """
    uid = models.UUIDField(primary_key=True, default=uuid4, editable=False, help_text="Unique facility identifier")
    operator = models.ForeignKey(Company, on_delete=models.RESTRICT)
    country = CountryField()
    address = models.TextField(max_length=100)

    class Meta:
        verbose_name_plural = 'Facilities'
        unique_together = ['country', 'address', 'operator']
        ordering = ['operator', 'country', 'address']
    
    def __str__(self):
        return self.address.replace('\r\n', ', ')

class Metadata(models.Model):
    """Transparency information related to a ProductItem."""
    registration_number = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    issuer = models.ForeignKey(Institution, on_delete=models.PROTECT)
    reo = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name='Responsible economic operator', help_text="The entity bearing legal responsibility for the DPP and the product.")
    creation_date = models.DateField(auto_now_add=True)
    last_modified = models.DateField(auto_now=True)
    version = models.CharField(max_length=20)
    language = models.CharField(max_length=20, default='EN', help_text="Language used in descriptions")
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
    issuer = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.SET_NULL, help_text="Author, issuer or publisher")
    instructions = models.ManyToManyField(Instruction, blank=True, help_text="Select all that apply. Instructions included in this document (ony for manauals)")
    language = models.CharField(max_length=40, blank=True)
    # file_type = models.CharField(max_length=5, default=file.split('.')[-1])
    issue_date = models.DateTimeField(default=datetime.date.today)
    expiry_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.file.name.split('/')[-1]
    @property
    def filename(self):
        return self.file.name.split('/')[-1]

@receiver(m2m_changed, sender=Document.instructions.through)
def validate_instructions(sender, instance, action, **kwargs):
    """Ensure that all and only manuals have instructions."""
    if action == "post_add" or action == "post_remove" or action == "post_clear":
        manuals = instance.DOCUMENT_TYPES['Manuals']
        if instance.type in manuals and not instance.instructions.exists():
            raise ValidationError("A manual must have at least one instruction type.")
        if instance.instructions.exists() and instance.type not in manuals:
            raise ValidationError("Instructions can only be associated with manuals.")


## Technosphere: products and processes

class Flow(models.Model):
    """Base class for (physical) flows of components and producs.
    """
    def __str__(self):
        if hasattr(self, "productmodel"):
            return str(self.productmodel)
        elif hasattr(self, "productbatch"):
            return str(self.productbatch)

        return f"Unspecified flow #{self.pk}"
    
    @property
    def model(self):
        if hasattr(self, "productmodel"):
            return self.productmodel
        elif hasattr(self, "productbatch"):
            return self.productbatch.model
        else:
            return self

class ProductModel(Flow):
    """Describes a specific model or version of a product.
    All items of a product model share the same design, weight, and manufacturer.
    """
    name = models.CharField("Model or product name", max_length=100)
    unit = models.CharField(max_length=15, default='pcs', help_text="How the product is counted, e.g. pcs, bottles, sheets, kWh")
    brand = models.CharField(max_length=50, blank=True)
    description = models.TextField(max_length=200, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    taric_code = models.CharField("TARIC code", max_length=20, blank=True, help_text="(customs code)")
    hs_code = models.CharField("HS code", max_length=10, blank=True, help_text="Harmonized System classification (customs code)")

    def __str__(self):
        return self.name
    
    @property
    def manufacturer(self):
        """Get the manufacturer of this product (operator of the
        Facility hosting the Process that produces this ProductModel).
        """
        if hasattr(self, 'produced_by'):
            return self.produced_by.facility.operator
        else:
            return None
    
    #TODO: only works for linear supply chains. No infinite loop detection. Fix with Leontief matrix.
    def calc_composition(self, main_line):
        """
        Recursively collect the Composition of components,
        by searching upstream processes.
        Returns a dict of {crm_id: country_code}.
        """
        composition = defaultdict(float)
        
        # Use known composition for this product, if it comes from background
        if not hasattr(self, 'produced_by') or self.produced_by.production_line != main_line:
            if any(bom := self.composition.all()):
                for entry in bom:
                    composition[entry.material] = entry.quantity * CONVERSIONS[entry.unit] * 1000
            return composition
        
        # Recurse into components
        for input in self.produced_by.prod_exchanges.filter(type__in=['prod', 'waste']):
            component_bom = input.product.model.calc_composition(main_line)
            plm = -1 if input.type == 'waste' else 1 # Subtract waste materials
            for material, value in component_bom.items():
                composition[material] += input.amount * value * plm
        return composition

    def get_composition(self, recalculate=False):
        """Make a Composition table for this product.
        Calculate from supply chain if needed.
        Returns a QuerySet with all materials
        """
        if hasattr(self, 'produced_by') and (recalculate or not self.composition.all()):
            production_line = self.produced_by.production_line
            composition = self.calc_composition(production_line)
            if len(composition) == 0:
                print("No material composition specified for any component.")
            for mat, value in composition.items():
                Composition.objects.update_or_create(
                    product=self, material=mat, defaults={'quantity': value}
                )
        return self.composition.all()
    
    def get_hazardous_concentrations(self):
        """Returns a dict with the concentration of each hazardous material"""
        concentrations = defaultdict(float)
        try:
            product_weight = self.properties.weight * CONVERSIONS[self.properties.weight_unit.unit]
        except ProductProperties.DoesNotExist:
            print(f"Weight of {self} unknown; cannot calculate concentration.")
        bom = self.get_composition()
        for content in bom:
            if isinstance(mat := content.material, HazardousMaterial):
                concentrations[mat] += content.quantity * CONVERSIONS[content.unit] / product_weight
        return concentrations
    
    def find_missing_bom(self):
        """Find direct components without a composition"""
        if not hasattr(self, 'produced_by'):
            return []
        missing = []
        for flow in self.produced_by.prod_exchanges.filter(type__in=['prod', 'waste']):
            # Check if this flow has any composition data
            if not any(flow.product.composition.all()):
                missing.append(flow)
        return missing
    
    def add_concentrations(self):
        """Make a Concentration table for this product, using Composition.
        Also add the packaging ratio to the Concentration table.
        """
        concentrations = self.get_hazardous_concentrations()
        
        for material, frac in concentrations.items():
            Concentration.objects.update_or_create(
                product=self, material=material, fraction=frac
            )
        packaging = Material.objects.update_or_create(name='Total packaging material')
        if hasattr(self, 'properties'):
            Concentration.objects.update_or_create(
                product=self,
                material=packaging,
                fraction=self.properties.packaging_ratio,
            )

    def add_components(self):
        """Make a Component table for this product, using exchange data.
        """
        if hasattr(self, 'produced_by_other'):
            activity = self.produced_by_other
        elif hasattr(self, 'produced_by'):
            activity = self.produced_by
        
        for exch in activity.prod_exchanges.filter(type='prod', direction='in'):
            Component.objects.update_or_create(
                product=self, component=exch.product, amount=exch.amount / activity.amount
            )
    
    def add_subcomponents(self, component):
        """
        Add all subcomponents of `component` to this product.
        If a subcomponent already exists, its amount is increased.
        """
        this_entry = Component.objects.filter(product=self, component=component)
        if not this_entry.exists():
            raise Component.DoesNotExist(
                f"'{self}' does not contain component '{component}'"
            )
        subcomponents = component.composed_of.all()
        if not subcomponents.exists():
            print(f"No components found for {component}")
            return
        with transaction.atomic():
            for subcomp in subcomponents:
                # Update, or if component already exists, sum amounts
                new_amount = this_entry.amount * subcomp.amount
                Component.objects.update_or_create(
                    product=self,
                    component=subcomp.component,
                    defaults={'amount': models.F('amount') + new_amount},
                )
            this_entry.delete()

class ProductBatch(Flow):
    batch_number = models.PositiveIntegerField()
    model = models.ForeignKey(Flow, on_delete=models.RESTRICT, related_name='batch')
    
    class Meta:
        verbose_name_plural = 'Product batches'
    def __str__(self):
        return f"{self.model} batch {self.batch_number}"
    def clean(self):
        if not hasattr(self.model, "productmodel"):
            raise ValidationError("Model must be a ProductModel")

class ProductProperties(models.Model):
    """Physical properties of a product."""
    product = models.OneToOneField(Flow, on_delete=models.CASCADE, related_name='properties')
    weight = models.FloatField("Weight of 1 unit", validators=[MinValueValidator(0)])
    weight_unit = models.CharField(max_length=2, choices=UNIT_CHOICES['Mass'], default='kg')
    volume = models.FloatField(validators=[MinValueValidator(0)])
    volume_unit = models.CharField(max_length=3, choices=UNIT_CHOICES['Volume'], default='m3')
    includes_packaging = models.BooleanField("The above includes packaging", default=False)
    density = models.FloatField(validators=[MinValueValidator(0)], help_text='Density of the product, excluding packaging and empty space.')

    @property
    def density_unit(self):
        return f"{self.weight_unit}/{self.volume_unit}"
    @property
    def packaging_ratio(self):
        if self.weight == 0:
            return 0
        package_weight = 0
        for pack in self.produced_by.prod_exchanges.filter(type='pack'):
            package_weight += pack.properties.weight * CONVERSIONS[pack.weight_unit]
        if self.includes_packaging:
            return package_weight / (self.weight - package_weight)
        else:
            return package_weight / self.weight
    @property
    def net_weight(self):
        if self.includes_packaging:
            return self.weight / (self.packaging_ratio + 1)
        else:
            return self.weight
        
    
class DppDetails(models.Model):
    """Detailed info about a product, as required for the Digital Product Passport (DPP).
    Typically needed for final products sold in stores.
    """
    product = models.OneToOneField(Flow, on_delete=models.CASCADE, primary_key=True)
    importer = models.ForeignKey(Importer, blank=True, null=True, on_delete=models.SET(get_unknown_importer), related_name='imported_products', help_text="Specify if the product is imported from outside the EU.")
    origin = models.ForeignKey(Company, on_delete=models.SET(get_unknown_company), related_name="manufactured_products")  #FIXME: duplicate info

    #Classification
    CPV_code = models.CharField(max_length=20, blank=True, help_text="Common Procurement Vocabulary code")
    GS1_GPC_code = models.CharField(max_length=20, blank=True, help_text="Global Product Classification code")

    # Documents and other quality compliance info
    quality_compliance_documents = models.ManyToManyField(Document, blank=True)
    warranty_period = models.DecimalField(default=0, max_digits=3, decimal_places=1, validators=[MinValueValidator(0)], help_text="Warranty period in years")
    spare_parts_availability_duration = models.DecimalField(default=0, max_digits=3, decimal_places=1, validators=[MinValueValidator(0)], help_text="Spare parts availability in years")
    takeback_system = models.CharField(max_length=10, choices={'no': 'No take-back system', 'basic': 'Collection on request', 'active': 'Structured take-back with dedicated channels or collection points', 'advanced': 'Certified, traceable take-back system'}, default='no')

    class Meta:
        verbose_name = verbose_name_plural = "DPP details"

    def __str__(self):
        return f"Details for {self.product}"

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

class ProductItem(models.Model):
    product_batch = models.ForeignKey(ProductBatch, on_delete=models.PROTECT)
    DPP_metadata = models.OneToOneField(Metadata, on_delete=models.PROTECT, blank=True)
    serial_number = models.CharField(max_length=50, unique=True)  #FIXME: make only the combination of product and manufacturer unique?
    GTIN_code = models.CharField(max_length=20, help_text="Global Trade Item Number (or comparable)")
    production_date = models.DateField(default=datetime.date.today)
    circularity = models.CharField(max_length=50, default="new")

    def update_circularity(self, circularity_code):
        """Append circularity_code to self.circularity"""
        allowed_values = ['R3', 'R5', 'R6', 'R7', 'R8', '-']
        assert circularity_code in allowed_values, (
            "Expecting one of the following circularity codes: " +
            ', '.join(allowed_values)
        )
        self.circularity += ',' + circularity_code
        self.save()

    def __str__(self):
        return f"Product #{self.serial_number}"
    
    def disassemble(self):
        """
        Creates a ProductItem for each component.
        Returns a list of created ProductItems.
        """
        created_items = []
        
        for i, component in enumerate(self.components.all()):  #TODO: make this table
            component_serial = f"{self.serial_number}-C{i}"
            for j in range(component.amount):
                # Generate unique serial number for each component
                if component.amount > 1:
                    component_serial += f"-{j}"
                
                new_item = ProductItem.objects.create(
                    product_batch=component,
                    serial_number=component_serial,
                    GTIN_code="",  # Components may not have GTIN initially
                    production_date=self.production_date,
                )
                created_items.append(new_item)
        
        return created_items

class Emission(models.Model):
    name = models.CharField(max_length=50)
    unit = models.CharField(max_length=10, default='g')

    def __str__(self):
        return self.name


## Technosphere: Activities and Exchanges

class Activity(models.Model):
    name = models.CharField(max_length=100)
    amount = models.FloatField(default=1, help_text="Reference number of units produced")
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, help_text="Production location", blank=True, null=True)
    description = models.TextField(max_length=300, blank=True)

    class Meta:
        verbose_name_plural = "Activities"

    def __str__(self):
        return self.name

class ManufacturingProcess(Activity):
    """Aggregated manufacturing process that will be published
    along with a DPP.
    """
    functional_flow = models.OneToOneField(Flow, on_delete=models.RESTRICT, verbose_name="Main product", related_name='produced_by_other', help_text="The output product of this manufacturing process.")
    modified_at = models.DateField(auto_now=True)
    # mass_balance = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='mass_balance', help_text="A document showing all material exchanges of the process.")
    # energy_balance = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='energy_balance', help_text="A document showing all energy flows exchanges of the process.")

    def clean(self):
        if not self.facility:
            raise ValidationError({
                'facility': "'Facility' cannot be blank. Please specify it."
            })

class ProductionLine(models.Model):
    """Describes a part of a supply chain, operated by one manufacturer.
    Used to support data collection, not published is DPP.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=300, blank=True)
    final_product = models.OneToOneField(Flow, on_delete=models.RESTRICT, verbose_name="Final product", help_text="The output product of this production line")
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, help_text="Production location", blank=True, null=True)
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
        process_list = self.bop.all()
        unused_outputs = []
        
        for process in process_list:
            # Check if this process's output is used as input in any Exchange
            func_flow = process.functional_flow
            is_linked = ProductExchange.objects.filter(
                product=func_flow, process__in=process_list
            ).exists()
            
            if not is_linked and func_flow != self.final_product:
                unused_outputs.append(func_flow)
        
        if unused_outputs:
            product_names = ', '.join([str(p) for p in unused_outputs])
            return f"Warning: Products [{product_names}] are not linked to other processes."
        
        return ""  # All good

class Process(Activity):
    """Internal subprocess, used for convenient modeling of a production line"""
    production_line = models.ForeignKey(ProductionLine, on_delete=models.CASCADE, related_name='bop')
    functional_flow = models.OneToOneField(Flow, blank=True, null=True, on_delete=models.SET_NULL, verbose_name="Main output", related_name='produced_by')
    is_outsourced = models.BooleanField("Outsourced", default=False)
    created_at = models.DateField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.functional_flow:
            raise ValidationError("'Main output' cannot be blank. Please select a product.")

    def save(self, *args, **kwargs):
        # If facility is not set, default to production line facility
        if self.production_line:
            if self.facility:
                self.is_outsourced = (self.facility != self.production_line.facility)
            else:  # not self.facility
                self.facility = self.production_line.facility
        
        self.clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Processes"

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

class BackgroundProcess(ManufacturingProcess):
    created_at = models.DateField(auto_now_add=True)
    database = models.CharField(max_length=50, blank=True)
    db_code = models.CharField(max_length=50, blank=True, help_text="Unique ID in the source database")
    tags = models.CharField(max_length=150, blank=True)
    type = models.CharField(max_length=50, blank=True)

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
    is_observed = models.BooleanField("Quantity is", choices={True: "Measured", False: "Modeled or calculated"}, default=False)
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
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='exchanged_by')
    process = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='prod_exchanges')
    FLOW_TYPES = {
        'prod': 'Component (part of the product)',
        'cons': 'Consumable',
        'ener': 'Electricity or heat',
        'util': 'Utility or equipment',
        'serv': 'Service',
        'pack': 'Packaging',
        'react': 'Reactant',
        'waste': 'Waste',
    }
    type = models.CharField(max_length=5, choices=FLOW_TYPES)

    class Meta:
        unique_together = ['product', 'process', 'direction']
        ordering = ['process', 'product']

    def clean(self):
        if (self.direction == 'out') & (self.type != 'waste'):
            raise ValidationError("'Type' of output flow must be 'waste'.")

    def save(self, *args, **kwargs):
        # If type is not set, default to part or waste
        if not self.type:
            if self.direction == 'in':
                self.type = 'prod'
            else:
                self.type = 'waste'
        
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.direction}: {self.amount} {self.product.model.unit} {self.product}"

class EnvExchange(Exchange):
    """Represents an emission or resource extraction by a process."""
    COMPARTMENTS = {
        'Air': {
            'air-urban': 'Urban air', # close to ground
            'air-rural': 'Non-urban air or from high stacks',
            'air-lt': 'Long-term', # and low population density
            'air-indoor': 'Indoor',
            'air-strato': '10-30 km above ground', # 'lower stratosphere + upper troposphere'
            'air': 'Unspecified',
        },
        'uptake': 'Direct human uptake',
        'Soil': {
            'soil-agri': 'Agricultural',
            'soil-forest': 'Forest',
            'soil-indu': 'Industrial',
            'soil': 'Unspecified',
        },
        'Water': {
            'surface_water': 'Surface water',
            'seawater': 'Seawater',
            'groundwater': 'Groundwater',
            'groundwater-lt': 'Groundwater, long term',
            'groundwater-deep': 'Deep underground wells',
            'water': 'Unspecified',
        },
    }
    substance = models.ForeignKey(Emission, on_delete=models.CASCADE, related_name='exchanges')
    process = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='env_exchanges')
    compartment = models.CharField(max_length=20, choices=COMPARTMENTS)

    class Meta:
        unique_together = ['process', 'substance', 'compartment', 'direction']
        ordering = ['process', 'substance']
        verbose_name = 'Emission or Extraction'
        verbose_name_plural = 'Emissions & Extractions'

    def clean(self):
        if self.direction == 'ff':
            raise ValidationError("'Direction' must be either 'input' or 'output'.")

    def save(self, *args, **kwargs):
        if not self.direction:
            self.direction == 'out'
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.direction}: {self.amount} {self.substance.unit} {self.substance}"

class Alias(models.Model):
    """Allow companies to define an alternative product name to display"""
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='alias')
    user = models.ForeignKey(Company, on_delete=models.CASCADE)
    alt_name = models.CharField("Display name", max_length=100)

    class Meta:
        verbose_name_plural = "Aliases"

    def __str__(self):
        return f"{self.product} = {self.alt_name}"

class Transport(models.Model):
    """Table of transport distance and vehicle
    for inputs to a production line.
    """
    VEHICLES = {
        'ocean': 'Ship (ocean)',
        'NA': 'Unspecified',
    }
    production_line = models.ForeignKey(ProductionLine, on_delete=models.CASCADE, related_name='transport')
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='transport')
    distance = models.PositiveSmallIntegerField("Transport distance (km)", default=0, validators=[MaxValueValidator(40000)])
    mode = models.CharField("Main mode of transport", max_length=10, choices=VEHICLES, default='NA')

    def __str__(self):
        return f"{self.distance} km by {self.VEHICLES[self.mode]}"


## Composition and Materials

class Material(models.Model):
    name = models.CharField("Material name", max_length=50)
    density = models.FloatField(blank=True, default=0)
    recycled_fraction = models.FloatField("Recycled content (%)", default=0, validators=FRACTION_VALIDATOR)
    recyclable_fraction = models.FloatField("Recyclable material (%)", default=0, validators=FRACTION_VALIDATOR)
    biobased_fraction = models.FloatField("Bio-based material (%)", default=0, validators=FRACTION_VALIDATOR)
    # reused_fraction = models.FloatField("Reused material (%)", default=0, validators=FRACTION_VALIDATOR) #FIXME: N/A
    renewable_fraction = models.FloatField("Sustainable and renewable material (%)", default=0, validators=FRACTION_VALIDATOR)
    chemical_formula=models.CharField(max_length=30, blank=True)

    criticality_level = models.CharField(max_length=1, blank=True, default='', choices={'': 'N/A', 'c': 'critical', 'h': 'high', 'm': 'intermediate'}, help_text="Only for Critical Raw Materials (CRMs): criticality indicator based on supply risk and economic importance.")
    origin_country = CountryField("Country of origin", blank=True, null=True, help_text="Only for Critical Raw Materials (CRMs)")

    def __str__(self):
        if self.origin_country:
            return f"{self.name} ({self.origin_country.code})"
        else:
            return self.name

    class Meta:
        # unique_together = ('name', 'origin_country')  # If always the same %'s
        ordering = ['name', 'origin_country']

    def clean(self):
        if bool(self.criticality_level) != bool(self.origin_country):
            raise ValidationError({
                'criticality_level': "If this is a CRM, 'Country of origin' must also be specified.",
                'origin_country': "If this is a CRM, 'Criticality level' must also be specified.",
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class HazardousMaterial(Material):
    CAS_number = models.CharField(max_length=50, blank=True, unique=True)
    safety_instructions = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='material_safety_instructions')  # (SafetyDataSheet)
    # substance_location = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='material_location')

class Composition(models.Model):
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='composition')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='used_in')
    quantity = models.FloatField(help_text="The amount of material present in product.")
    unit = models.CharField(max_length=2, choices=UNIT_CHOICES['Mass'], default='g')

    class Meta:
        unique_together = ('product', 'material')
        ordering = ['product', 'material']
    
    def __str__(self):
        return f"{self.quantity} {self.unit} {self.material} (in {self.product})"

class Concentration(models.Model):
    """Describes the concentration fo Substances of Concern in a product,
    and the ratio of packaging vs. product weight.
    """
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='concentration')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='concentration_in')
    fraction = models.FloatField(validators=FRACTION_VALIDATOR)

    class Meta:
        unique_together = ('product', 'material')
        ordering = ['product', 'material']
    
    def __str__(self):
        return f"{self.fraction:.1%} {self.material} (in {self.product})"

class Component(models.Model):
    """Describes (replaceable) components contained in products.
    Sometimes called 'Bill of Materials'.
    This information is always derived from exchanges.
    """
    product = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='composed_of')
    component = models.ForeignKey(Flow, on_delete=models.PROTECT, related_name='part_of')
    amount = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Replaceable component"
        unique_together = ('product', 'component')
        ordering = ['product', 'component']

    def clean(self):
        if self.product == self.component:
            raise ValidationError("A product cannot contain itself as a component.")

    def __str__(self):
        return f"{self.amount} x {self.component} (in {self.product})"


## Service and maintenance records

class LifeCycleEvent(models.Model):
    """An activity or event during the life cycle of a product item.
    In line with UNTP Traceability Event.
    """
    EVENT_TYPES = {
        'sales': 'Sales or ownership transfer',
        'test': 'Inspection',
        'Maintenance': {
            'corrective': 'Repair',
            'software': 'Software update',
            'performance': 'Performance upgrade',
            'safety': 'Safety improvement',
            'energy_optimization': 'Energy optimization',
            'compliance': 'Compliance update',
            'other': 'Other maintenance',
        },
        'disassembly': 'Disassembly',
        'Closing the loop': {
            'R3': 'Reuse',
            'R5': 'Refurbish',
            'R6': 'Remanufacture',
            'R7': 'Repurpose',
        },
        'End-of-life treatment': {
            'recycling': 'Recycling',
            'landfill': 'Landfilling',
            'incineration': 'Incineration',
            'stockpiling': 'Stockpiling',
            'disposal': 'Disposal (unspecified)',
        },
    }
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    product = models.ForeignKey(ProductItem, on_delete=models.CASCADE, related_name='service_events')
    operator = models.ForeignKey(ServiceOperator, on_delete=models.CASCADE, help_text="Entity that performs this event.")
    type = models.CharField(max_length=30, choices=EVENT_TYPES)
    date = models.DateField(auto_now_add=True)

    # Link to LCA activity
    def get_empty_activity():
        unknown, created = ManufacturingProcess.objects.get_or_create(name="Empty activity")
        return unknown
    activity_data = models.ForeignKey(ManufacturingProcess, default=get_empty_activity, on_delete=models.SET_DEFAULT, help_text="Activity describing the inputs and outputs (optional).")

    def clean(self):
        if self.service_type == 'maintenance' and not self.maintenance_plan:
            raise ValidationError("Maintenance plan must be attached for maintenance services.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        event = self.EVENT_TYPES[self.type]
        return f"{event} of a {self.product.product_batch.name}"

class InspectionEvent(LifeCycleEvent):
    diagnostic_results = models.ManyToManyField(Document, blank=True)

class MaintenanceEvent(LifeCycleEvent):
    """Describes maintenance, repair, refurbishment, and similar events.
    """
    description = models.TextField(max_length=300)
    maintenance_plan = models.ForeignKey(Document, on_delete=models.RESTRICT)
    # Modifications fields
    affected_functionality = models.CharField(max_length=200, blank=True)
    software_or_hardware = models.BooleanField(choices={True: "Software", False: "Hardware"})

    # Repair (i.e. corrective maintenance) fields
    root_cause = models.TextField(max_length=300, blank=True)
    diagnostics_performed = models.TextField(max_length=300, blank=True) #FIXME: remove, is a separate event
    corrective_action = models.TextField(max_length=300, blank=True)  #FIXME: remove, same as description

class DisassemblyEvent(LifeCycleEvent):
    """Describes detachment of components from a ProductItem.
    NOTE: self.product is the *input* being disassembled.
    """
    def save(self, *args, **kwargs):
        for component in self.product.disassemble():
            ItemExchange.objects.create(item=component, event=self, amount=-1)
        super().save(*args, **kwargs)


class ItemExchange(models.Model):
    """Describes where individual product/component items are used (positive)
    or produced (negative values).
    Can be used for component replacement, disassembly, and closing a loop.
    """
    item = models.ForeignKey(ProductItem, on_delete=models.CASCADE)
    event = models.ForeignKey(LifeCycleEvent, on_delete=models.CASCADE)
    amount = models.SmallIntegerField(help_text="Inputs are positive, outputs are negative.")

    def clean(self):
        super().clean()
        allowed_events = LifeCycleEvent.EVENT_TYPES['Maintenance'].keys() + LifeCycleEvent.EVENT_TYPES['Closing the loop'].keys() + ['disassembly']
        if self.event.type not in allowed_events:
            raise ValidationError("This life cycle event cannot exchange items.")
    
    def __str__(self):
        arrow = '<-' if self.amount < 0 else '->'
        return f"{abs(self.amount)} {self.item} {arrow} {self.event}"


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

class SustainabilityEvaluation(models.Model):
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
        return str(datetime.date.today().year)
    
    product = models.ForeignKey(Flow, on_delete=models.CASCADE)
    functional_amount = models.FloatField()
    system_boundaries = models.CharField(max_length=200, blank=True)
    geographical_scope = models.CharField(max_length=4, choices=GEO_CHOICES, blank=True)
    temporal_scope = models.CharField(max_length=50, default=get_year)
    impact_assessment_method = models.CharField(max_length=50, blank=True, help_text="Specify the environmental impact assessment method. E.g. EF 3.0, ReCiPe, ILCD, TRACI.")
    software_used = models.CharField(max_length=50, blank=True, help_text="Indicate the assessment software used. E.g. OpenLCA, GaBi, SimaPro, Umberto.")
    allocation_method = models.CharField(max_length=6, blank=True, choices={'mass': 'Mass-based', 'econom': 'Economic (price-based)', 'energy': 'Energy-based', 'other': 'Other'}, help_text="How are impacts allocated for co-production processes?")
    assessment_date = models.DateField(default=datetime.date.today)
    assessed_by = models.ForeignKey(Institution, blank=True, null=True, on_delete=models.PROTECT)

    @property
    def reference_flow(self):
        return self.product
    @property
    def functional_unit(self):  # literally the unit
        return self.product.model.unit
    
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
    """A circularity evaluation of a certain product model/batch."""
    product = models.ForeignKey(Flow, on_delete=models.CASCADE)
    assessment_date = models.DateField(default=datetime.date.today, help_text="When the assessment was made or updated.")
    assessed_by = models.ForeignKey(Institution, blank=True, null=True, on_delete=models.PROTECT)
    report = models.ForeignKey(Document, blank=True, null=True, on_delete=models.SET_NULL, related_name='circularity_eval', help_text="Report describing the circularity assessment, and manual for monitoring and updating the circularity metrics.")

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
    uncertainty = models.CharField(max_length=100, blank=True)
    comment = models.TextField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.indicator.name}: {self.value}"

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


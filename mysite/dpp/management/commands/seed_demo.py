"""Load a synthetic demo dataset: the battery cooling plate use case.

    python manage.py seed_demo              # load (once)
    python manage.py seed_demo --reset      # remove the demo data and load it again
    python manage.py seed_demo --remove     # remove the demo data only

All names, addresses and numbers are invented for testing and demonstrations.
They are not measurements or real company data.
"""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from dpp.models import (
    BackgroundProcess, Company, Component, Composition, DppDetails, Emission, EnvExchange, Facility,
    ImpactCategory, ImpactIndicator, Institution, ManufacturingProcess, Material, Metadata, Process,
    ProductBatch, ProductExchange, ProductItem, ProductModel, ProductProperties,
    ProductionLine, Publisher, SustainabilityEvaluation, SustainabilityScore,
    Transport,
)

DEMO_USER = "demo"
LINE_NAME = "Battery cooling plate line (demo)"
MANUFACTURER = "DemoTherm Automotive GmbH"
SUPPLIER = "Demo Aluminium Rolling B.V."
LCA_TEAM = "Demo LCA team (synthetic values)"
FINAL_PRODUCT = "Battery cooling plate BCP-400"
SERIAL_PREFIX = "DEMO-BCP-"

# Products bought from suppliers: name -> (unit, transport km, mode)
PURCHASED = {
    "Aluminium sheet EN AW-3003, 1.5 mm": ("kg", 650, "truck"),
    "Aluminium filler wire AlSi12": ("kg", 420, "truck"),
    "Argon, welding grade": ("m3", 120, "truck"),
    "Helium, leak-test grade": ("m3", 120, "truck"),
    "Alkaline degreasing agent": ("kg", 300, "truck"),
    "Tap water": ("kg", 0, "NA"),
    "Electricity, medium voltage, DE": ("kWh", 0, "NA"),
}
INTERMEDIATE = {
    "Cooling plate halves, degreased": "pcs",
    "Cooling plate, welded": "pcs",
}
WASTE = {"Aluminium scrap": "kg"}  # sent to a recycler 80 km away by truck
MATERIALS = {
    # name -> fields
    "Aluminium alloy EN AW-3003": dict(density=2730, recycled_fraction=0.35, recyclable_fraction=0.95),
    "Silicon metal": dict(density=2330, recyclable_fraction=0.5, criticality_level="c", origin_country="CN"),
}
EXAMPLES_DIR = Path(settings.BASE_DIR) / "dss" / "examples"


def gtin13(first12: str) -> str:
    """Add the GS1 check digit to a 12-digit number."""
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return first12 + str((10 - total % 10) % 10)


class Command(BaseCommand):
    help = "Load a synthetic demo dataset (battery cooling plate) for testing and demonstrations."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove existing demo data first, then load it again.")
        parser.add_argument("--remove", action="store_true", help="Only remove the demo data.")
        parser.add_argument("--password", help="Password for the 'demo' user (default: a random one, printed once).")
        parser.add_argument("--no-dss", action="store_true", help="Skip creating the decision-support example sessions.")

    def handle(self, *args, **opts):
        if opts["remove"] or opts["reset"]:
            remove_demo_data()
            self.stdout.write("Removed the demo data.")
            if opts["remove"]:
                return
        if ProductionLine.objects.filter(name=LINE_NAME).exists():
            self.stdout.write(self.style.WARNING("Demo data is already loaded. Use --reset to load it again."))
            return

        password = opts["password"] or secrets.token_urlsafe(9)
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=DEMO_USER, defaults={"first_name": "Demo", "last_name": "User", "email": "demo@example.org"}
            )
            if created or opts["password"]:
                user.set_password(password)
                user.save()
            line = load_demo_data(user)

        self.stdout.write(self.style.SUCCESS(f"Loaded the demo data: {line} (id {line.pk})."))
        if created or opts["password"]:
            self.stdout.write(f"Log in as '{DEMO_USER}' with password: {password}")

        if not opts["no_dss"]:
            for label, links in create_dss_sessions().items():
                self.stdout.write(f"Decision support example ({label}): {links}")


def load_demo_data(user) -> ProductionLine:
    """Create the demo organisations, products, production line and passport."""
    # ── Organisations and site ──
    manufacturer = Company.objects.create(
        name=MANUFACTURER, country="DE", address="Musterstraße 12, 70173 Stuttgart",
        contact_email="info@demotherm.example", website="https://demotherm.example", vat_number="DE000000000",
    )
    supplier = Company.objects.create(
        name=SUPPLIER, country="NL", address="Voorbeeldweg 3, 5600 AA Eindhoven",
        contact_email="sales@demo-aluminium.example", vat_number="NL000000000B01",
    )
    lca_team = Institution.objects.create(name=LCA_TEAM, country="NL", type="research")
    plant = Facility.objects.create(operator=manufacturer, country="DE", address="Werkstraße 5, 70565 Stuttgart (demo plant)")
    supplier_site = Facility.objects.create(operator=supplier, country="NL", address="Voorbeeldweg 3, Eindhoven (demo site)")

    # ── Materials ──
    materials = {name: Material.objects.create(name=name, **fields) for name, fields in MATERIALS.items()}

    # ── Products ──
    final = ProductModel.objects.create(
        name=FINAL_PRODUCT, unit="pcs", brand="DemoTherm", hs_code="761699",
        description="Brazing-free aluminium cooling plate for an EV battery module, joined by dynamic beam laser welding.",
    )
    products = {name: ProductModel.objects.create(name=name, unit=unit) for name, (unit, *_ ) in PURCHASED.items()}
    products.update({name: ProductModel.objects.create(name=name, unit=unit) for name, unit in INTERMEDIATE.items()})
    products.update({name: ProductModel.objects.create(name=name, unit=unit) for name, unit in WASTE.items()})

    # ── Production line and processes ──
    line = ProductionLine.objects.create(
        name=LINE_NAME, created_by=user, facility=plant, final_product=final,
        description="Degreasing, dynamic beam laser welding and leak testing of battery cooling plates.",
    )
    degreasing = Process.objects.create(
        name="Alkaline degreasing", production_line=line, amount=1,
        functional_flow=products["Cooling plate halves, degreased"],
        description="Spray degreasing of both plate halves before joining.",
    )
    welding = Process.objects.create(
        name="Dynamic beam laser welding", production_line=line, amount=1,
        functional_flow=products["Cooling plate, welded"],
        description="Joining the two halves with a dynamic beam laser, 2.4 m weld seam.",
    )
    leak_test = Process.objects.create(
        name="Helium leak test", production_line=line, amount=1, functional_flow=final,
        description="Final tightness test of the cooling channels.",
    )

    def add(process, product_name, amount, type_, direction="in", **extra):
        ProductExchange.objects.create(
            process=process, product=products[product_name], amount=amount, type=type_, direction=direction, **extra
        )

    add(degreasing, "Aluminium sheet EN AW-3003, 1.5 mm", 1.95, "prod", is_observed=True)
    add(degreasing, "Alkaline degreasing agent", 0.02, "cons")
    add(degreasing, "Tap water", 1.5, "cons")
    add(degreasing, "Electricity, medium voltage, DE", 0.15, "ener")
    add(degreasing, "Aluminium scrap", 0.10, "waste", direction="out")

    add(welding, "Cooling plate halves, degreased", 1, "prod")
    add(welding, "Aluminium filler wire AlSi12", 0.002, "cons", uncertainty_type="interval", minimum=0.0015, maximum=0.0025)
    add(welding, "Argon, welding grade", 0.008, "cons")
    add(welding, "Electricity, medium voltage, DE", 0.42, "ener", is_observed=True)
    particulates, _ = Emission.objects.get_or_create(name="Particulate Matter, < 2.5 um", defaults={"unit": "g"})
    EnvExchange.objects.create(process=welding, substance=particulates, amount=0.01, direction="out", compartment="air-urban")

    add(leak_test, "Cooling plate, welded", 1, "prod")
    add(leak_test, "Helium, leak-test grade", 0.002, "cons")
    add(leak_test, "Electricity, medium voltage, DE", 0.05, "ener")

    # Stand-ins for the average market processes that normally come from the LCA
    # database, so that every input (and the waste) has a known origin.
    for name in [*PURCHASED, *WASTE]:
        BackgroundProcess.objects.create(
            name=f"market for {name}", functional_flow=products[name], facility=supplier_site,
            database="Demo stand-in (no LCA data)", type="market",
        )

    for name, (_, km, mode) in PURCHASED.items():
        Transport.objects.create(production_line=line, product=products[name], distance=km, mode=mode, utilisation_ratio=0.6)
    Transport.objects.create(production_line=line, product=products["Aluminium scrap"], distance=80, mode="truck", utilisation_ratio=0.6)

    # ── Final product: properties, composition, DPP details ──
    ProductProperties.objects.create(
        product=final, weight=1.85, weight_unit="kg", volume=0.00068, volume_unit="m3", density=2730,
    )
    Composition.objects.create(product=final, material=materials["Aluminium alloy EN AW-3003"], quantity=1840, unit="g")
    Composition.objects.create(product=final, material=materials["Silicon metal"], quantity=0.24, unit="g")
    DppDetails.objects.create(
        product=final, CPV_code="34300000", warranty_period=5, spare_parts_availability_duration=10,
        takeback_system="basic",
    )

    # ── Publishing settings and one published passport ──
    gtin = gtin13("200000000001")
    publisher = Publisher.objects.create(
        production_line=line, amount=50, gtin=gtin, issuer=manufacturer, reo=manufacturer, version="1.0",
        language="EN", access_link_base="https://www.l4m-dss.eu/dpp/final/", credential_format="json_ld",
        storage_location=2, audit_trail_mechanism=1, update_interval="E",
    )
    run_publishing_steps_1_to_4(line, publisher)
    batch = ProductBatch.objects.create(model=final, batch_number=202611, GTIN=gtin)
    item = ProductItem.objects.create(product_batch=batch, serial_number=f"{SERIAL_PREFIX}0001")
    Metadata.objects.create(
        product_item=item, issuer=manufacturer, reo=manufacturer, version="1.0", language="EN",
        credential_format="json_ld", storage_location=2, audit_trail_mechanism=1, update_interval="E",
    )

    # ── A sustainability evaluation with synthetic scores ──
    climate, _ = ImpactCategory.objects.get_or_create(name="Climate change")
    gwp, _ = ImpactIndicator.objects.get_or_create(
        method="EF 3.1", impact_category=climate, unit="kg CO2-eq",
        defaults={"description": "Global warming potential, 100 years"},
    )
    evaluation = SustainabilityEvaluation.objects.create(
        product=final, functional_amount=1, system_boundaries="Cradle to gate", geographical_scope="EU",
        impact_assessment_method="EF 3.1", software_used="Brightway 2.5", allocation_method="mass",
        assessed_by=lca_team,
    )
    SustainabilityScore.objects.create(
        impact_indicator=gwp, evaluation=evaluation, impact_value=25.4,
        upstream_phase=0.93, manufacturing_phase=0.07, scope_1_2_3=25.4,
    )
    return line


def run_publishing_steps_1_to_4(line, publisher):
    """Run the publishing steps that need no LCA database (as Publisher.run_from_step does).
    Step 5, the life cycle assessment, needs Brightway and is left to the user."""
    message = line.check_missing_origins() + line.check_unused_outputs() + publisher.check_details(line.final_product)
    if message:
        raise RuntimeError(f"Demo data incomplete: {message}")
    line.aggregate_production()
    product = line.final_product.model
    product.add_concentrations()
    product.add_components()
    line.create_transport()
    publisher.status = 4
    publisher.error_message = ""
    publisher.save()


def remove_demo_data():
    """Delete everything load_demo_data() created, in an order the foreign keys allow."""
    with transaction.atomic():
        Metadata.objects.filter(product_item__serial_number__startswith=SERIAL_PREFIX).delete()
        ProductItem.objects.filter(serial_number__startswith=SERIAL_PREFIX).delete()
        ProductBatch.objects.filter(model__name=FINAL_PRODUCT).delete()
        ProductionLine.objects.filter(name=LINE_NAME).delete()  # also processes, exchanges, transport, publisher
        names = [FINAL_PRODUCT, *PURCHASED, *INTERMEDIATE, *WASTE]
        BackgroundProcess.objects.filter(functional_flow__productmodel__name__in=names).delete()
        ManufacturingProcess.objects.filter(functional_flow__productmodel__name__in=names).delete()  # aggregated line
        Component.objects.filter(product__productmodel__name__in=names).delete()
        ProductModel.objects.filter(name__in=names).delete()  # also properties, composition, DPP details, evaluations
        Material.objects.filter(name__in=MATERIALS).delete()
        Facility.objects.filter(operator__name__in=[MANUFACTURER, SUPPLIER]).delete()
        Company.objects.filter(name__in=[MANUFACTURER, SUPPLIER]).delete()
        Institution.objects.filter(name=LCA_TEAM).delete()


def create_dss_sessions() -> dict:
    """Start decision-support sessions from the example platform requests.
    Returns links to the first wizard step."""
    from django.urls import reverse
    from dss.serializers import ExperimentComparisonSerializer, WeldStationComparisonSerializer
    from dss.views import calculate_kpis

    links = {}
    for label, file, serializer, user in [
        ("process developer", "pd_experiments.json", ExperimentComparisonSerializer, "pd"),
        ("key account manager", "kam_welding_stations.json", WeldStationComparisonSerializer, "kam"),
    ]:
        data = json.loads((EXAMPLES_DIR / file).read_text())
        validated = serializer(data=data)
        validated.is_valid(raise_exception=True)
        session = calculate_kpis(validated.validated_data, user=user)
        links[label] = reverse("wizard", kwargs={"token": session.token, "step": 0})
    return links

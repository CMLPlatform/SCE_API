from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction

from dpp.models import (
    Company,
    Facility,
    Process,
    ProductExchange,
    ProductModel,
    ProductionLine,
    Transport,
)
from mysite.utils import UncertainValue


def add_input(
    process, line, name, unit, amount, exchange_type, flow_data=None, **exchange_fields
):
    input_product, _ = ProductModel.objects.update_or_create(name=name, unit=unit)
    exchange = ProductExchange(
        process=process,
        product=input_product,
        amount=float(amount),
        direction="in",
        type=exchange_type,
        **exchange_fields,
    )

    if isinstance(amount, UncertainValue):
        exchange.amount = amount.mean
        exchange.uncertainty_type = "interval" if amount.is_uncertain else "none"
        if amount.is_uncertain:
            exchange.minimum = amount.min
            exchange.maximum = amount.max

    exchange.save()
    if flow_data is not None:
        Transport.objects.create(
            production_line=line,
            product=input_product,
            distance=flow_data["transport_km"],
            mode=flow_data["transport_mode"],
        )

@transaction.atomic
def build_supply_chain(exp: dict, created_by: User | None = None) -> int:
    """Convert validated weld-station data as a production line."""
    if created_by is None or not created_by.is_authenticated:
        raise PermissionDenied(
            "An authenticated user is required to create a supply chain."
        )
    if exp["weldSpeed"] <= 0:
        raise ValueError("weldSpeed must be greater than zero.")

    manufacturer_data = exp["manufacturer"]
    manufacturer = Company.objects.create(
        name=manufacturer_data["name"],
        address=manufacturer_data.get("address", ""),
        country=manufacturer_data["country"],
        contact_email=manufacturer_data.get("contact_email", ""),
        website=manufacturer_data.get("website", ""),
        vat_number=manufacturer_data.get("vat_number", ""),
    )
    facility = Facility.objects.create(
        operator=manufacturer,
        country=exp["country"],
        address=manufacturer.address,
    )

    # Create the output product
    product = ProductModel.objects.create(
        name=f"Welded product for experiment {exp['experimentId']}",
        unit="pcs",
    )
    line = ProductionLine.objects.create(
        name=f"Weld station experiment {exp['experimentId']}",
        final_product=product,
        facility=facility,
        created_by=created_by,
    )
    process = Process.objects.create(
        name="Laser welding",
        production_line=line,
        functional_flow=product,
        facility=facility,
        amount=1 - exp["scrapRate"],
    )

    # Create the material inputs
    for material in exp["materials"]:
        add_input(
            process,
            line,
            material["name"],
            "kg",
            material["weight"],
            "prod",
            flow_data=material,
        )

    # Create the consumables
    processing_time = exp["weldLength"] / exp["weldSpeed"]
    unit_conversion = {
        "kg": ("kg", 1.0),
        "g":  ("kg", 1e-3),
        "mg": ("kg", 1e-6),
        "m3": ("m3", 1.0),
        "L":  ("m3", 1e-3),
        "l":  ("m3", 1e-3),
    }
    seconds_per_time = {"h": 3600, "min": 60, "s": 1}
    for consumable in exp["consumables"]:
        try:
            quantity_unit, time_unit = consumable["unit"].split("/")
            product_unit, qnt_factor = unit_conversion[quantity_unit]
            time_factor = seconds_per_time[time_unit]
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"Unsupported consumable unit: {consumable['unit']!r}."
            ) from exc

        amount = (
            consumable["flowRate"] * qnt_factor * processing_time / time_factor
        )
        add_input(
            process,
            line,
            consumable["name"],
            product_unit,
            amount,
            "cons",
            flow_data=consumable,
        )

    # Create the electricity input
    cycle_time = exp.get("cycleTime", processing_time)
    electricity = (
        processing_time * exp["laserPowerkW"]
        + cycle_time * exp["weldingStationPowerkW"]
    ) / 3600
    add_input(
        process,
        line,
        f"Electricity, low voltage, grid mix {exp['country']}",
        "kWh",
        electricity,
        "ener",
    )

    # Connect to pre-/post-processes
    for step in (*exp["preprocesses"], *exp["postprocesses"]):
        add_input(
            process,
            line,
            f"{step['name']} service",
            "min",
            step["time"],
            "serv",
        )

    return line.pk

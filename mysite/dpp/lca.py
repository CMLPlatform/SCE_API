"""Toolbox with functions for doing LCA calculations,
and to import and export DPP data to Brightway.
"""
import datetime
import functools
import json
import logging
import re
import time
import requests

from pathlib import Path
import pandas as pd
from django.conf import settings

import bw2data as bwd
from bw2calc.errors import EmptyBiosphere
import bw2io as bwi
from sentier_brightway import import_db


class DppDataError(Exception):
    """The DPP data is incomplete. The message tells the user what to add."""


logger = logging.getLogger(__name__)

RESOURCE_UNITS = [
    'kg', 'g', 'lb', 'oz', 'l', 'cm3', 'dm3', 'm3', 'ft3', 'gal',
    'liters', 'cubic meters', 'cubic feet', 'gallons',
    'kWh', 'MWh', 'MJ', 'GJ',
]
# for cat in ['Mass', 'Volume', 'Energy']:
#     RESOURCE_UNITS += list(UNIT_CHOICES[cat].keys()) + list(UNIT_CHOICES[cat].values())

# Methods that are too detailed (for (in)organics)
# Sub-indicators that split a main indicator into organics and inorganics.
# Both naming styles: "ecotoxicity: freshwater, inorganics" (ecoinvent) and
# "Ecotoxicity, freshwater_inorganics" (sentier).
EXCLUDED_METHODS = re.compile(r"[,_]\s*(in)?organics$")
DPP_PROJECT = "L4M-DPP"
BIOSPHERE = "ecoinvent-3.12-biosphere"
ECOINVENT = "ecoinvent-3-12-cutoff"
BONSAI_DB = "BONSAI v2.4.0"
BAFU_DB = "bafu-2026"

CACHE_DIR = Path.cwd() / "_cache"
BONSAI_EXPORT_DIR = Path.cwd() / "bonsai_data"
CACHE_DIR.mkdir(exist_ok=True)
BONSAI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Project setup and database import
# ---------------------------------------------------------------------------

country_data = pd.read_csv(settings.DATA_DIR / "country_data.csv", index_col="country")

def project_status(project_name: str) -> dict[str, bool]:
    """Check if all databases in a project are fully processed.

    A database counts as True only if its processed file exists on disk
    (an import that failed half-way leaves only a registered DB).
    Returns {db_name: processed}, or {} if the project does not exist.
    """
    if project_name not in bwd.projects:
        return {}
    bwd.projects.set_current(project_name)
    return {
        name: Path(bwd.Database(name).filepath_processed()).is_file()
        for name in bwd.databases
    }

def installed_databases(project_name: str = DPP_PROJECT) -> list[str]:
    """Names of the fully imported background databases.

    Leaves out biosphere databases, and the "dpp_" databases that hold the
    app's own LCA results: they are not a source of background processes.
    """
    return [db for db, ok in project_status(project_name).items()
            if ok and 'biosphere' not in db and not db.startswith('dpp_')]

def find_activities(database: str, text: str, limit: int = 5) -> list[dict]:
    """Search `database` for activities that match `text`.

    Returns:
        list[dict]: keys 'code', 'name', 'location' and 'unit'.
    """
    return [
        {key: act.get(key, '') for key in ('code', 'name', 'location', 'unit')}
        for act in bwd.Database(database).search(text, limit=limit)
    ]

def staged_bonsai_export(export_dir: Path|None=None) -> tuple[Path, dict]:
    """
    The export staged in the cache with its units fixed, plus the BONSAI -> biosphere map.

    v2.4.0 labels standing wood "standard cubic meter", ecoinvent "cubic meter", and the
    importer's unit library does not know the former. For solid wood the two are the same
    volume, so the label is aligned 1:1. The export itself is not modified.
    """
    export_dir = export_dir or BONSAI_EXPORT_DIR
    export_files = [
        "io_metadata.json", "product_value_table.gzip",
        "technosphere_value_table.gzip", "extensions_value_table.gzip",
        "index_table_technosphere.gzip", "index_table_extensions.gzip",
    ]
    stage = CACHE_DIR / "bonsai_export"
    stage.mkdir(exist_ok=True)
    for name in export_files:
        link = stage / name
        link.unlink(missing_ok=True)
        if name != "io_metadata.json":
            link.symlink_to((export_dir / name).resolve())

    metadata = json.loads((export_dir / "io_metadata.json").read_text(encoding="utf-8"))
    biosphere = bwd.Database(bwd.config.biosphere)
    to_biosphere = {}
    for code, flow in metadata.items():
        if "compartment" not in flow or not flow.get("source_id"):
            continue  # unlinked flows go to "<database> biosphere"
        target = biosphere.get(code=flow["source_id"])
        to_biosphere[code] = target["code"]
        if flow.get("unit") == "standard cubic meter" and target["unit"] == "cubic meter":
            print(f"  unit aligned 1:1 to 'cubic meter': {flow['name']}")
            flow["unit"] = "cubic meter"
    (stage / "io_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return stage, to_biosphere

class BonsaiImporter():
    """
    Replacement for `from bw2io.importers.bonsai import BonsaiImporter`,
    which requires a fork of bw2io. For now, we stick to core bw2io.
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError()

def import_bonsai() -> None:
    """Import the BONSAI database using a staged export approach."""
    stage, to_biosphere = staged_bonsai_export()
    importer = BonsaiImporter(stage, BONSAI_DB, b3mapping=to_biosphere)
    importer.apply_strategies()
    importer.write_database()

def setup_project(project_name: str=DPP_PROJECT, background="BAFU") -> None:
    """Initialize the project if needed. Add biosphere and background DB
    and check the completeness.
    """
    status = project_status(project_name)

    if project_name not in bwd.projects:
        logger.debug("Creating a new Brightway project setup.")
    if background=="BAFU" and (BAFU_DB not in status or not status[BAFU_DB]):
        import_db(project=project_name, overwrite=False)
    elif BIOSPHERE not in status or not status[BIOSPHERE]:
        scratch = f"{project_name}_setup"
        bwd.projects.set_current(scratch)
        bwi.remote.install_project(project_key=BIOSPHERE,
                project_name=project_name, overwrite_existing=True)
        bwd.projects.set_current(project_name)
        bwd.projects.delete_project(scratch, delete_dir=True)
    else:
        bwd.projects.set_current(project_name)
    if background=="BONSAI" and (BONSAI_DB not in status or not status[BONSAI_DB]):
        started = time.perf_counter()
        logger.info(f"  importing {BONSAI_DB} from {BONSAI_EXPORT_DIR} …")
        if BONSAI_DB in bwd.databases: # left behind by an import that failed half-way
            logger.info(f"  removing an incomplete '{BONSAI_DB}'")
            del bwd.databases[BONSAI_DB]
        import_bonsai()
        logger.info(f"  done in {time.perf_counter() - started:,.0f} s")
    
    # Check and log the new status
    for db, present in project_status(project_name).items():
        logger.info(f"{db:<10} {'present' if present else 'MISSING'}")


def ensure_methods(family: str):
    """
    Make sure that the LCIA family and all its methods exist
    in the DPP database.
    Returns: IndicatorSet
    """
    # Import here to avoid circular imports
    from .models import IndicatorSet, ImpactIndicator, ImpactCategory

    try:
        method_set = IndicatorSet.objects.get(name=family)
    except IndicatorSet.DoesNotExist:
        logger.debug("Creating a set of environmental indicators.")
        method_set = IndicatorSet.objects.create(
            name=family, start_date=datetime.date.today()
        )
    methods = select_methods(family)
    names = [indicator_name(m, family) for m in methods]
    unknown_category, _ = ImpactCategory.objects.get_or_create(name='Unknown')
    for m, name in zip(methods, names):
        ImpactIndicator.objects.update_or_create(
            method=name,
            indicator_set=method_set,
            defaults={'unit': bwd.methods[m].get('unit') or ''},
            create_defaults={'unit': bwd.methods[m].get('unit') or '',
                             'impact_category': unknown_category, 'is_environmental': True},
        )
    # Remove indicators of methods that are not used any more, unless they have scores
    ImpactIndicator.objects.filter(indicator_set=method_set, sustainabilityscore__isnull=True
                                   ).exclude(method__in=names).delete()
    return method_set

def indicator_name(method: tuple, family: str) -> str:
    """The impact category of a Brightway method: the element after the family name.

    ('ecoinvent-3.12', 'EF v3.1', 'climate change', 'GWP100') -> 'climate change'
    ('sentier', 'EF v3.1', 'Climate change') -> 'Climate change'
    """
    return method[method.index(family) + 1]

def _method_biosphere(method: tuple) -> str | None:
    """The biosphere database that the characterisation factors of `method` use."""
    try:
        key = bwd.Method(method).load()[0][0]
        node = bwd.get_node(id=key) if isinstance(key, int) else bwd.get_activity(key)
        return node['database']
    except Exception:
        return None

def select_methods(family: str) -> list[tuple]:
    """The Brightway methods of `family` to calculate, sorted, from one source only.

    A project can hold the same family from more than one source, for example
    ('ecoinvent-3.12', 'EF v3.1', ...) and ('sentier', 'EF v3.1', ...). Each source
    uses its own biosphere database. We use the source whose biosphere the installed
    background databases use, so that their emissions are counted.
    """
    sources = {}
    for m in bwd.methods:
        if family in m and not EXCLUDED_METHODS.search(indicator_name(m, family)):
            sources.setdefault(m[:m.index(family)], []).append(m)
    if len(sources) > 1:
        used = {dep for db in installed_databases() for dep in bwd.databases[db].get('depends', [])}
        matching = [s for s, ms in sources.items() if _method_biosphere(ms[0]) in used]
        chosen = matching[0] if matching else sorted(sources)[0]
        logger.debug(f"{family}: using the methods of {chosen or 'no source'}, of {list(sources)}.")
        return sorted(sources[chosen])
    return sorted(next(iter(sources.values()), []))

def prompt_choice(title: str, options: list, default_index: int = 0):
    """Simple numbered menu. CC-BY EMPA"""
    yellow = "\033[1;33m"
    green = "\033[1;32m"
    reset = "\033[0m"
    print(f"\n{yellow}{title}{reset}")
    for idx, opt in enumerate(options, 1):
        default_marker = " (default)" if idx - 1 == default_index else ""
        print(f"{green}  {idx}) {opt}{default_marker}{reset}")
    ans = input(f"{yellow}Select option:{reset} ").strip()
    if not ans:
        return options[default_index]
    try:
        idx = int(ans) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except Exception:
        pass
    print("Invalid choice, using default.")
    return options[default_index]


# ---------------------------------------------------------------------------
# Conversion and communication functions
# ---------------------------------------------------------------------------

def bonsai_api(endpoint: str) -> list:
    """Pages of BONSAI API endpoint (no account needed), cached in CACHE_DIR.
    Examples of `endpoint`: 'products/', 'activities/', 'product-corr/'
    """
    # Load data from cache if available
    path = CACHE_DIR / f"bonsai_api_{endpoint.strip('/')}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    rows = []
    url = "https://lca.aau.dk/api/" + endpoint
    while url:
        page = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
        page.raise_for_status()
        data = page.json()
        rows += data["results"]
        url = (data.get("next") or "").replace("http://", "https://")
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def get_or_create_bw_process(dpp_product):
    raise NotImplementedError()
    return

def get_biosphere_db():
    """Get the biosphere database of the currently active project."""
    databases = list(bwd.databases)
    for name in [BIOSPHERE, "ef-3.1-biosphere"]:
        if name in databases:
            return bwd.Database(name)
    for name in databases:
        if "biosphere" in name:
            return bwd.Database(name)
    raise FileNotFoundError(f"No biosphere database found in {bwd.projects.current}.")

# Units of biosphere flows -> units of Emission objects
BIOSPHERE_UNITS = {
    'cubic meter': 'm3',
    'cubic meter-year': 'm3-yr',
    'kilo Becquerel': 'kBq',
    'kilogram': 'kg',
    'megajoule': 'MJ',
    'square meter': 'm2',
    'square meter-year': 'm2-yr',
    'standard cubic meter': 'Nm3',
}

# Published mapping (randonneur_data) from ecoinvent biosphere flows to EF 3.1 flows.
# The ecoinvent 3.11 mapping also covers the flows that ecoinvent 3.12 kept.
EF_FLOW_MAPPING = "ecoinvent-3.11-biosphere-EF-3.1-biosphere"

@functools.cache
def _ecoinvent_to_ef_codes() -> dict[str, str]:
    """{ecoinvent biosphere flow code: EF 3.1 biosphere flow code}"""
    from randonneur_data import Registry
    data = Registry().get_file(EF_FLOW_MAPPING)
    return {entry['source']['uuid']: entry['target']['uuid'] for entry in data['replace']}

def lca_biosphere(family: str) -> str | None:
    """The biosphere database that the methods of `family` characterise, or None."""
    methods = select_methods(family)
    return _method_biosphere(methods[0]) if methods else None

def translate_biosphere_flow(key: tuple, target: str | None) -> tuple | None:
    """The flow in biosphere `target` that stands for `key`, a flow of another biosphere.

    Returns `key` unchanged when it is already in `target` (or `target` is None),
    and None when there is no matching flow.
    """
    database, code = key
    if target is None or database == target:
        return key
    if database.startswith('ecoinvent') and target.lower().startswith('ef-3.1'):
        ef_code = _ecoinvent_to_ef_codes().get(code)
        if ef_code:
            try:
                bwd.get_node(database=target, code=ef_code)
                return (target, ef_code)
            except Exception:
                return None
    return None

def emission_amount(exc, flow_unit: str) -> float | None:
    """The amount of EnvExchange `exc` in `flow_unit`, the unit of its biosphere flow.

    Returns None when the units cannot be converted (for example g to m3).
    """
    from .models import UNIT_CHOICES, CONVERSIONS
    unit, target = exc.substance.unit, BIOSPHERE_UNITS.get(flow_unit, flow_unit)
    if unit == target:
        return exc.amount
    for group in UNIT_CHOICES.values():
        if isinstance(group, dict) and unit in group and target in group:
            return exc.amount * CONVERSIONS[unit] / CONVERSIONS[target]
    return None

def biosphere_to_dpp_flows():
    """Convert all biosphere flows to Emission objects"""
    from .models import Emission
    unit_map = BIOSPHERE_UNITS
    setup_project()
    biosphere_db = get_biosphere_db()
    bio_flows = set((i['name'], i['unit']) for i in list(biosphere_db))
    if len(bio_flows) <= len(Emission.objects.all()): return
    for name, unit in bio_flows:
        if unit in unit_map:
            unit = unit_map[unit]
            Emission.objects.update_or_create(name=name, unit=unit)

def find_biosphere_flow(exc, biosphere_db):
    compartment_map = {
        'air-urban': ('air', 'urban air close to ground'),
        'air-rural': ('air', 'non-urban air or from high stacks'),
        'air-lt': ('air', 'low population density, long-term'),
        'air-indoor': ('air', 'indoor'),  # Doesn't exist
        'air-strato': ('air', 'lower stratosphere + upper troposphere'),
        'air': ('air',),
        'uptake': ('direct human uptake',),  # Doesn't exist
        'soil-agri': ('soil', 'agricultural'),
        'soil-forest': ('soil', 'forestry'),
        'soil-indu': ('soil', 'industrial'),
        'soil': ('soil',),
        'surface_water': ('water', 'surface water'),
        'seawater': ('water', 'ocean'),
        'groundwater': ('water', 'ground-'),
        'groundwater-lt': ('water', 'ground-, long-term'),
        'groundwater-deep': ('water', 'fossil well'),
        'water': ('water',),
    }
    name = exc.substance.name.lower()
    categories = compartment_map[exc.compartment]
    if exc.direction == "in":
        if 'soil' in categories:
            categories = ('natural resource', 'in ground')
        elif 'air' in categories:
            categories = ('natural resource', 'in air')
        elif 'water' in categories:
            if 'fossil well' in categories:
                categories = ('natural resource', 'fossil well')
            else:
                categories = ('natural resource', 'in water')
        else:
            categories = ('natural resource', 'biotic')

    for act in biosphere_db:
        if act["name"].lower() == name and categories == act.get("categories"):
            return (act['database'], act['code'])

    # If exact match fails: search name
    act = biosphere_db.search(name)[0]
    return (act['database'], act['code'])

def make_transport_exchange(transports, product, amount):
    """Create an exchange that represent the transport service
    of `amount` of `product`, with distance specified in `transports`.

    Parameters:
        transports: QuerySet of Transport table
        product: ProductModel, input to some process
        amount: int, amount of product transported
    
    Returns:
        Brightway exchange, describing transport input
    """
    # Import here to avoid circular imports
    from .models import UNIT_CHOICES, CONVERSIONS
    ecoinvent_codes = {
        "train": '44760b3d59b51d5aaffecedeba08e3fa', # freight train, average, EU
        "ocean ship": '1d2cb4018daf428aebf419380c6a2975', # sea freight container ship, GLO
        "truck": 'dd736ab7d965646d04b091ae5fa68d97',  # lorry, unspecified, RER
        "inland ship": '1d510fd336c629c3687f812967538191', # inland waterways, RER
        "airplane": '96a835b204d1d9327b56bca7995dc24f', # aircraft, unspecified, GLO
        "delivery van": '558949a7ddfcccba760eab39bda68e88', # light commercial vehicle, EU
        "NA": 'dd736ab7d965646d04b091ae5fa68d97', #FIXME defaults to truck for now
    }
    bafu_codes = {
        "train": 'aacc6120-0e68-3835-8303-5ae37d62c030', # freight train, average, EU
        "ocean ship": 'dc299788-d8c5-3adc-b025-d607edd4d973', # sea freight container ship, GLO
        "truck": '99f8a4b0-99b5-3130-924c-5de4c10b62ef',  # lorry, fleet average, RER
        "inland ship": 'missing', # inland waterways, RER
        "airplane": '1313d894-5c0a-38cd-b06c-fcce93e52cf9', # aircraft, medium-haul, GLO
        "delivery van": 'c21996a4-ec68-361e-8fda-dc3ad1081e7d', #FIXME Operation, van, CH
        "NA": '99f8a4b0-99b5-3130-924c-5de4c10b62ef', #FIXME defaults to truck for now
    }
    bonsai_codes = {
        "train": "M_TLAND_ALL",
        "ocean ship": "M_TWATR_ALL",
        "truck": "M_TLAND_ALL",
        "inland ship": "M_TWATR_ALL",
        "airplane": "C_TAIR",
        "delivery van": "M_TLAND_ALL",
        "NA": "M_TLAND_ALL",
    }
    transport = transports.filter(product=product).first()
    if transport is None:
        raise LookupError(f"No transport specified for {product}")
    # Determine the mass of one unit of product (kg)
    input_prod = transport.product
    if hasattr(input_prod, 'properties'):
        mass = input_prod.properties.weight * CONVERSIONS[
            input_prod.properties.weight_unit
        ]
    elif input_prod.model.unit in UNIT_CHOICES['Mass']:
        mass = CONVERSIONS[input_prod.model.unit]
    else:
        mass = 1

    # Calculate transport distance (t-km) or price (MEuro)
    if ECOINVENT in bwd.databases:
        exchange = {
            "input": (ECOINVENT, ecoinvent_codes[transport.mode]),
            "amount": mass / 1000 * amount * transport.distance,
            "type": "technosphere",
            "unit": 'ton kilometer',
        }
    elif BAFU_DB in bwd.databases:
        if bafu_codes[transport.mode] == 'missing':
            raise DppDataError(
                f"The BAFU database has no process for transport by "
                f"{transport.get_mode_display()}. Choose another mode of transport for {product}."
            )
        exchange = {
            "input": (BAFU_DB, bafu_codes[transport.mode]),
            "amount": mass / 1000 * amount * transport.distance,
            "type": "technosphere",
            "unit": 'ton kilometer',
        }
    elif BONSAI_DB in bwd.databases:
        transp_code = bonsai_codes[transport.mode]
        price = country_data.loc["?", transp_code + "_price"]  #FIXME: country
        exchange = {
            "input": (BONSAI_DB, transp_code),
            "amount": mass * amount * transport.distance * price / 1e9,
            # units: kg/pcs * pcs   *    km              * EUR/t-km -> MEuro
            "type": "technosphere",
            "unit": 'MEUR',
        }
    return exchange

def list_background_processes() -> dict:
    """
    Create a dictionary of available background processes
    Structured as: {database_name: {activity_name: activity_code}}
    """
    setup_project()
    background = {}
    for db_name in bwd.databases:
        if db_name[:4] != "dpp_":
            background[db_name] = {
                act["name"]: act["code"]
                for act in bwd.Database(db_name)
            }
    return background


# ---------------------------------------------------------------------------
# Create DPP LCA and do LCA calculations
# ---------------------------------------------------------------------------

def convert_dpp_to_brightway(processes: list, db_name: str, target_biosphere: str | None = None):
    """
    Convert DPP processes to Brightway activities in db_name
    
    :param dpp_process: List of ManufacturingProcess
    :param db_name: Bightway database name, to add the activity to.
    :param target_biosphere: The biosphere database that the LCIA methods use.
        Emissions are matched in the default biosphere (get_biosphere_db), then
        moved to this one, so that the methods count them. None: do not move.
    """
    # Import here to avoid circular imports
    from .models import ProductExchange, EnvExchange, BackgroundProcess

    biosphere = get_biosphere_db()
    bw_activities = {}
    def background_key(process):
        """(database, code) of the Brightway activity that stands for `process`,
        or None when `process` is a DPP process that we must write ourselves."""
        background = BackgroundProcess.objects.filter(pk=process.pk).first()
        if background is None or not background.database:
            return None
        if background.database not in bwd.databases:
            raise DppDataError(
                f"The background process '{background.name}' links to the LCA database "
                f"'{background.database}', which is not installed. Link it to a process "
                f"in one of these databases: "
                f"{', '.join(db for db in bwd.databases if 'biosphere' not in db and not db.startswith('dpp_'))}."
            )
        key = (background.database, background.db_code)
        try:
            bwd.get_activity(key)
        except Exception:
            raise DppDataError(
                f"The background process '{background.name}' has the code "
                f"'{background.db_code}', which is not in '{background.database}'."
            ) from None
        return key

    for dpp_process in processes:
        if background_key(dpp_process):
            continue  # Already in a Brightway database, e.g. ecoinvent or BAFU

        location = str(dpp_process.facility.country) if dpp_process.facility else 'GLO'
        exchanges = [{
            "input": (db_name, dpp_process.pk),
            "amount": dpp_process.amount,
            "type": "production",  # Reference flow
            "unit": dpp_process.functional_flow.model.unit,
        }]
        if exchanges[0]['unit'] in RESOURCE_UNITS:
            stage = 'Raw material acquisition'
        else:
            stage = 'Manufacturing'
        for exc in ProductExchange.objects.filter(process=dpp_process):
            if exc.product.manufacturing_info not in processes:
                continue  # Cutoff in case max_depth was used.
            sign = 1 if exc.direction == 'in' else -1
            source = exc.product.manufacturing_info
            exchanges.append({
                "input": background_key(source) or (db_name, source.pk),
                "amount": sign * exc.amount,
                "type": "technosphere",
                "unit": exc.product.model.unit,
            })
            # Add transport exchange for this input product
            if sign == 1:
                # Only processes made by a production line have transport data
                transports = dpp_process.functional_flow.productionline.transport
                exchanges.append(
                    make_transport_exchange(transports, exc.product, exc.amount)
                )
        for exc in EnvExchange.objects.filter(process=dpp_process):
            found = find_biosphere_flow(exc, biosphere)
            flow = translate_biosphere_flow(found, target_biosphere)
            what = (f"The {exc.get_direction_display().lower()} '{exc.substance}' "
                    f"({exc.get_compartment_display()}) of '{dpp_process.name}'")
            if flow is None:
                raise DppDataError(
                    f"{what} has no match in the biosphere '{target_biosphere}' that the "
                    f"impact methods use, so it would not be counted. Choose another "
                    f"substance or compartment."
                )
            flow_unit = bwd.get_activity(flow).get('unit', '')
            amount = emission_amount(exc, flow_unit)
            if amount is None:
                raise DppDataError(
                    f"{what} is in '{exc.substance.unit}', which cannot be converted to "
                    f"'{flow_unit}', the unit of the biosphere flow. Change the unit."
                )
            exchanges.append({
                "input": flow,
                "amount": amount,
                "type": "biosphere",
                "unit": BIOSPHERE_UNITS.get(flow_unit, flow_unit),
            })
        
        activity = {
            "name": dpp_process.name,
            "reference product": str(dpp_process.functional_flow),
            "unit": dpp_process.functional_flow.model.unit,
            "location": location,
            "stage": stage,
            "comment": dpp_process.description,
            "exchanges": exchanges,
        }
        bw_activities[(db_name, dpp_process.pk)] = activity
    return bw_activities

def select_supply_chain(root_product, max_depth=None):
    """
    Traverse DPP links to build minimal Brightway database
    for a specific product's supply chain.
    """
    visited = set()
    processes_to_include = []
    
    def traverse(flow, depth=0):
        if (max_depth and depth > max_depth) or flow.id in visited:
            return
        visited.add(flow.id)
        
        # Get the ManufacturingProcess for this flow
        assert hasattr(flow, 'manufacturing_info'), (
            f"Product {flow} has no manufacturing process!"
        )
        process = flow.manufacturing_info
        processes_to_include.append(process)
        
        # Traverse upstream through exchanges
        if hasattr(process, 'prod_exchanges'):
            for exchange in process.prod_exchanges.all():
                traverse(exchange.product, depth + 1)
    
    traverse(root_product)
    return processes_to_include

def lca_calculations(activity, family: str = 'EF v3.1'):
    """Calculate LCA results for 1 unit of activity output. CC-BY EMPA
    
    :param activity: Brigtway activity
    :param family (str): Name of a LCIA method family
    """
    # Select methods belonging to family
    methods = select_methods(family)
    logger.debug(f"{len(methods)} EF methods found")
    if not methods:
        logger.warning(f"No {family} methods available.")
        raise RuntimeError(f"No {family} methods available.")
    # Calculate LCA results
    try:
        lca = activity.lca(methods[0])
    except EmptyBiosphere:
        raise DppDataError(
            f"The supply chain of '{activity['reference product']}' has no emissions "
            "or resource use, so there is nothing to assess. Add inputs or emissions "
            "to its processes, then run step 2 again."
        ) from None
    results = [(indicator_name(methods[0], family), lca.score, bwd.methods[methods[0]].get('unit'))]
    for m in methods[1:]:
        lca.switch_method(m)
        lca.lcia()
        results.append((indicator_name(m, family), lca.score, bwd.methods[m].get("unit")))
    return results

def create_supply_chain_lca(product):
    """
    Create a SustainabilityEvaluation by doing LCA
    for 1 unit of `product`.
    
    :param product: The final product for which to do LCA
    :type product: Flow
    """
    # Import here to avoid circular imports
    from .models import SustainabilityEvaluation, SustainabilityScore, ImpactIndicator
    
    setup_project()
    lcia_family = 'EF v3.1'
    method_set = ensure_methods(lcia_family)
    evaluation, created = SustainabilityEvaluation.objects.get_or_create(
        product=product,
        functional_amount=1,
        system_boundaries='Cradle to gate LCA',
        geographical_scope='c',
        impact_assessment_method=lcia_family, # method_set,
        software_used='Brightway + Lasers4MaaS tool',
        allocation_method='',
    )
    if not created:
        # Remove only the old scores of this assessment, not those of other products
        SustainabilityScore.objects.filter(evaluation=evaluation).delete()

    # Create unique Brightway database
    db_name = f"dpp_{product.model.name}_{product.pk}"
    if db_name in bwd.databases:
        merge_choice = "Overwrite"
        # merge_choice = prompt_choice(
        #     f"Foreground DB '{db_name}' exists. Choose action:",
        #     ["Add data", "Overwrite"],
        #     default_index=0,
        # )
        if merge_choice == "Overwrite":
            del bwd.databases[db_name]
        else:
            print("Adding to existing DB.")
        db = bwd.Database(db_name)
    else:
        db = bwd.Database(db_name)
        db.register()
    
    # Collect supply chain processes and load in Brightway DB
    processes = select_supply_chain(product)
    bw_activities = convert_dpp_to_brightway(processes, db.name, lca_biosphere(lcia_family))
    db.write(bw_activities)
    
    # # Link to background database (ecoinvent, etc.)
    # link_to_background_db(bw_activities, background_db)
    
    # Perform LCA
    ref_activity = db.get(product.manufacturing_info.pk)
    results = lca_calculations(ref_activity, lcia_family)
    #TODO: contribution analysis
    # Create SustainabilityScores to store results
    if created:
        for m, value, unit in results:
            SustainabilityScore.objects.create(
                impact_indicator=ImpactIndicator.objects.get(method=m,indicator_set=method_set),
                evaluation=evaluation,
                impact_value=value,
                upstream_phase=0,
                manufacturing_phase=0,
                use_phase=0,
                end_of_life_phase=0,
                scope_1_2_3=0,
            )
    else:
        for m, value, unit  in results:
            SustainabilityScore.objects.update_or_create(
                impact_indicator=ImpactIndicator.objects.get(method=m, indicator_set=method_set),
                evaluation=evaluation,
                impact_value=value,
                upstream_phase=0,
                manufacturing_phase=0,
                use_phase=0,
                end_of_life_phase=0,
                scope_1_2_3=0,
            )
    
    return evaluation

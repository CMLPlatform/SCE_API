"""Basic outline and functions for doing LCA calculations,
and to import and export DPP data to Brightway.
"""
import bw2data as bwd
import bw2io as bwi
import datetime
import logging

logger = logging.getLogger(__name__)

RESOURCE_UNITS = [
    'kg', 'g', 'lb', 'oz', 'l', 'cm3', 'dm3', 'm3', 'ft3', 'gal',
    'liters', 'cubic meters', 'cubic feet', 'gallons',
    'kWh', 'MWh', 'MJ', 'GJ',
]
# for cat in ['Mass', 'Volume', 'Energy']:
#     RESOURCE_UNITS += list(UNIT_CHOICES[cat].keys()) + list(UNIT_CHOICES[cat].values())

# Methods that are too detailed (for (in)organics)
EXCLUDED_METHODS = {
    "ecotoxicity: freshwater, inorganics', 'comparative toxic unit for ecosystems (CTUe)",
	"ecotoxicity: freshwater, organics', 'comparative toxic unit for ecosystems (CTUe)",
	"human toxicity: carcinogenic, inorganics', 'comparative toxic unit for human (CTUh)",
	"human toxicity: carcinogenic, organics', 'comparative toxic unit for human (CTUh)",
	"human toxicity: non-carcinogenic, inorganics', 'comparative toxic unit for human (CTUh)",
	"human toxicity: non-carcinogenic, organics', 'comparative toxic unit for human (CTUh)')",
}
DEFAULT_REMOTE_PROJECT = "ecoinvent-3.12-biosphere"
ECOINVENT = "ecoinvent-3-12-cutoff"

def setup_project(project_name: str) -> None:
    """Initialize the project if needed, and check that it is complete."""
    if project_name not in bwd.projects:
        logger.debug("Creating a new Brightway project setup.")
        bwi.remote.install_project(DEFAULT_REMOTE_PROJECT, project_name)
    bwd.projects.set_current(project_name)

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
        method_set = IndicatorSet.objects.create(name=family, start_date=datetime.date.today())
    methods = [
        m for m in bwd.methods
        if family in m and m[-2:] not in EXCLUDED_METHODS
    ]
    if len(methods) < len(ImpactIndicator.objects.filter(indicator_set=method_set)):
        return method_set
    unknown_category, _ = ImpactCategory.objects.get_or_create(name='Unknown')
    for m in methods:
        ImpactIndicator.objects.update_or_create(
            method=m[-2],
            unit=bwd.methods[m].get('unit'),
            indicator_set=method_set,
            impact_category=unknown_category,
            is_environmental=True,
        )
    return method_set

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

def get_or_create_bw_process(dpp_product):
    raise NotImplementedError()
    return

def biosphere_to_dpp_flows():
    """Convert all biosphere flows to Emission objects"""
    from .models import Emission
    unit_map = {
        'cubic meter': 'm3',
        'cubic meter-year': 'm3-yr',
        'kilo Becquerel': 'kBq',
        'kilogram': 'kg',
        'megajoule': 'MJ',
        'square meter': 'm2',
        'square meter-year': 'm2-yr',
        'standard cubic meter': 'Nm3',
    }
    setup_project("L4M-DPP")
    biosphere_db = bwd.Database(DEFAULT_REMOTE_PROJECT)
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
    transport = transports.filter(product=product).first()
    if transport is None:
        raise LookupError(f"No transport specified for {product}")
    # Determine the mass of one unit of product (kg)
    input_prod = transport.product
    if hasattr(input_prod, 'properties'):
        mass = input_prod.properties.weight * CONVERSIONS[input_prod.properties.weight_unit]
    elif input_prod.unit in UNIT_CHOICES['Mass']:
        mass = CONVERSIONS[input_prod.unit]
    else:
        mass = 1

    return {  # Calculate transport distance (t-km)
        "input": (ECOINVENT, ecoinvent_codes[transport.mode]),
        "amount": mass / 1000 * amount * transport.distance,
        "type": "technosphere",
        "unit": 'ton kilometer',
    }

def convert_dpp_to_brightway(processes: list, db_name: str):
    """
    Convert DPP processes to Brightway activities in db_name
    
    :param dpp_process: List of ManufacturingProcess
    :param db_name: Bightway database name, to add the activity to.
    """
    # Import here to avoid circular imports
    from .models import ProductExchange, EnvExchange

    biosphere = bwd.Database(DEFAULT_REMOTE_PROJECT)
    bw_activities = {}
    for dpp_process in processes:
        location = str(dpp_process.facility.country) if dpp_process.facility else 'GLO'
        transports = dpp_process.functional_flow.productionline.transport
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
            try:
                source_db = exc.product.manufacturing_info.database
                db_code = exc.product.manufacturing_info.db_code
            except AttributeError:
                source_db = db_name
                db_code = exc.product.manufacturing_info.pk
            exchanges.append({
                "input": (source_db, db_code),
                "amount": sign * exc.amount,
                "type": "technosphere",
                "unit": exc.product.model.unit,
            })
            # Add transport exchange for this input product
            if sign == 1:
                exchanges.append(
                    make_transport_exchange(transports, exc.product, exc.amount)
                )
        for exc in EnvExchange.objects.filter(process=dpp_process):
            bioshpere_flow = find_biosphere_flow(exc, biosphere)
            exchanges.append({
                "input": bioshpere_flow,
                "amount": exc.amount,
                "type": "biosphere",
                "unit": exc.substance.unit,
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

def convert_bw_to_dpp(bw_activity):
    # Import here to avoid circular imports
    from .models import BackgroundProcess
    
    raise NotImplementedError()
    (db_name, code), act = bw_activity
    dpp_activity = BackgroundProcess(name=act.name, amount=1, description=act.comment, functional_flow=act.reference_product, database=db_name, db_code=code)
    for exchange in act.get('exchanges', []):
        if exchange.get('type') == 'technosphere':
            dpp_activity.amount = exchange['amount']
        else:
            pass #TODO: create an exchange
    return dpp_activity

def link_to_background_db(activities, background_db): #FIXME: unused
    """
    Link DPP processes to ecoinvent or other background DB
    only for processes not in DPP system.
    """
    for activity in activities:
        for exchange in activity.get('exchanges', []):
            if exchange.get('type') == 'technosphere':
                # If not in foreground, search background
                if not exchange.get('input'):
                    background_match = background_db.search(
                        exchange['name'], exchange.get('unit')
                    )
                    if background_match:
                        exchange['input'] = background_match

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
        assert hasattr(flow, 'manufacturing_info'), f"Product {flow} has no manufacturing process!"
        process = flow.manufacturing_info
        processes_to_include.append(process)
        # convert_dpp_to_bw_activity(process, db_name)
        
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
    methods = [
        m for m in bwd.methods
        if family in m and m[-2:] not in EXCLUDED_METHODS
    ]
    logger.debug(f"{len(methods)} EF methods found")
    if not methods:
        logger.warning(f"No {family} methods available.")
        raise RuntimeError(f"No {family} methods available.")
    methods = sorted(methods)
    # Calculate LCA results
    lca = activity.lca(methods[0])
    results = [(methods[0][-2], lca.score, bwd.methods[methods[0]].get('unit'))]
    for m in methods[1:]:
        lca.switch_method(m)
        lca.lcia()
        results.append((m[-2], lca.score, bwd.methods[m].get("unit")))
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
    
    setup_project("L4M-DPP")
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
        SustainabilityScore.objects.filter().delete()

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
    bw_activities = convert_dpp_to_brightway(processes, db.name)
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

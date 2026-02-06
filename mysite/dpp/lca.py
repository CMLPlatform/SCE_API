"""Basic outline and functions for doing LCA calculations,
and to import and export DPP data to Brightway.
"""
import brightway2 as bw
import bw2data as bwd
import bw2io as bwi
import uuid
from .models import *

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

def convert_dpp_to_brightway(processes: list, db_name: str):
    """
    Convert DPP processes to Brightway activities in db_name
    
    :param dpp_process: List of ManufacturingProcess
    :param db_name: Bightway database name, to add the activity to.
    """
    bw_activities = {}
    for dpp_process in processes:
        location = str(dpp_process.facility.country) if dpp_process.facility else 'GLO'
        exchanges = [{
            "input": (db_name, dpp_process.pk),
            "amount": dpp_process.amount,
            "type": "production",  # Reference flow
            "unit": dpp_process.functional_flow.model.unit,
        }]
        for exc in ProductExchange.objects.filter(process=dpp_process):
            # if exc.produced_by_other not in processes:
            #     continue  # Cutoff in case max_depth was used.
            sign = 1 if exc.direction == 'in' else -1
            try:
                source_db = exc.product.produced_by_other.database
            except AttributeError:
                source_db = db_name
            exchanges.append({
                "input": (source_db, exc.product.produced_by_other.pk),
                "amount": sign * exc.amount,
                "type": "technosphere",
                "unit": exc.product.model.unit,
            })
        
        activity = {
            "name": dpp_process.name,
            "reference product": str(dpp_process.functional_flow),
            "unit": dpp_process.functional_flow.model.unit,
            "location": location,
            "stage": 'Manufacturing',  #TODO
            "comment": dpp_process.description,
            "exchanges": exchanges,
        }
        bw_activities[(db_name, dpp_process.pk)] = activity
    return bw_activities

def convert_bw_to_dpp(bw_activity):
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
        
        # Get the production process for this item
        assert hasattr(flow, 'produced_by_other'), f"Product {flow} has no production process!"
        process = flow.produced_by_other
        processes_to_include.append(process)
        # convert_dpp_to_bw_activity(process, db_name)
        
        # Traverse upstream through exchanges
        if hasattr(process, 'prod_exchanges'):
            for exchange in process.prod_exchanges.all():
                traverse(exchange.product, depth + 1)
    
    traverse(root_product)
    return processes_to_include


def create_supply_chain_lca(product: Flow):
    # Create unique Brightway database
    db_name = f"dpp_{product.model.name}_{product.pk}"
    if db_name in bwd.databases:
        merge_choice = prompt_choice(
            f"Foreground DB '{db_name}' exists. Choose action:",
            ["Add data", "Overwrite"],
            default_index=0,
        )
        if merge_choice == "Overwrite":
            del bwd.databases[db_name]
        else:
            print("Adding to existing DB.")
        db = bwd.databases[db_name]
    else:
        db = bwd.Database(db_name)
        db.register()
    
    # Build minimal graph
    processes = select_supply_chain(product)
    bw_activities = convert_dpp_to_brightway(processes, db.name)
    db.write(bw_activities)
    
    # # Link to background database (ecoinvent, etc.)
    # link_to_background_db(bw_activities, background_db)
    
    # Perform LCA
    functional_unit = {db.get(product.produced_by_other.pk): 1}
    # Select methods belonging to EF3.1
    methods = []
    # Create SustainabilityEvaluation
    # Do multi-LCA
    for method in methods:
        lca = bw.LCA(functional_unit, method=('IPCC', 'GWP100'))
        lca.lci()
        lca.lcia()
        # Create SustainabilityScores
    
    return

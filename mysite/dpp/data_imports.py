from pathlib import Path
import pandas as pd
from django.conf import settings
# from django.contrib.auth.models import User
from dpp.models import CircularityIndicator, Instruction, ImpactIndicator, ImpactCategory
"""NOTE: to run this, use a command, I think manage.py runscript data_imports"""

def csv_to_django(file_path: Path | str, Model, relations={}):
    """
    Read data from a CSV file into a Django model.
    """

    # Convert DataFrame to list of model instances
    file_path = Path(file_path)
    df = pd.read_csv(file_path)
    fields = set([field.name for field in Model._meta.get_fields()])
    ignored = set(df.columns) - fields
    df = df.drop(columns=ignored)
    if any(ignored):
        print(f"Columns ignored because they can't be linked: {ignored}")
    for col, val in relations.items():
        df[col + '_id'] = val

    for _, row in df.iterrows():
        # new_object = Model(**row.to_dict())
        # new_object.save()
        Model(**row.to_dict()).save()

    print(f"{file_path.name} has been loaded as {Model.__name__} into the Django database.")


def __main__():
    circularity_csv = settings.DATA_DIR / "circularity_indicators.csv"
    csv_to_django(circularity_csv, CircularityIndicator)
    label_csv = settings.DATA_DIR / "document_labels.csv"
    csv_to_django(label_csv, Instruction)
    socioecon, _ = ImpactCategory.objects.get_or_create(name="Socio-economic impact")
    socioecon_csv = settings.DATA_DIR / "socioecon_indicators.csv"
    csv_to_django(socioecon_csv, ImpactIndicator, relations={"impact_category": socioecon.pk})

"""
R_CHOICES = {
    'R0 - Refuse': [
        ('hazardous', 'Hazardous substances'),
        ('fossil', 'Fossil energy use'),
        ('nonrenewable', 'Non-renewable materials'),
        ('other', 'Other materials'),
        ('consumption', 'Avoided product consumption'),
    ],
    'R1 - Rethink': [
        ('modularity', 'Modularity'),
        ('product_takeback', 'Product take-back'),  # Appears multiple times
        ('crm', 'Critical Materials'),
        ('shared_use', 'Shared use'),
        ('durability', 'Durability'),
        ('potential_use_during_lifetime', 'Potential use during lifetime'),
        ('multifunctionality', 'Multifunctionality'),
        ('modularity_score', 'Modularity score'),
        ('materials', 'Materials'),
        ('number_of_components', 'Number of components'),
        ('material_composition_complexity', 'Material composition complexity'),
        ('tools_required', 'Number of tools required'),
        ('separable_pieces_ratio', 'Separable pieces ratio'),
    ],
    'R2 - Reduce': [
        ('reduce_raw_materials_intensity', 'Raw materials intensity reduction'),
        ('reduce_energy_intensity', 'Energy intensity reduction'),
        ('reduce_energy_consumption', 'Energy consumption reduction'),
        ('reduce_waste_generation', 'Waste generation reduction'),
        ('reduce_material_losses', 'Material losses reduction'),
        ('reduce_water_intensity', 'Water intensity reduction'),
        ('reduce_water_consumption', 'Water consumption'),
    ],
    'R3 - Reuse': [
        ('reuse_rate', 'Reuse rate'),
        ('product_takeback', 'Product take-back'),
        ('consumer_awareness', 'Consumer awareness'),
        ('potential_use', 'Potential use'),
        ('ownership_time', 'Ownership time'),
        ('voidance_of_reuse_barriers', 'Voidance of reuse rarriers'),
        ('reuse_potential', 'Reuse potential'),
        ('costs_of_reuse', 'Costs of reuse'),
        ('access_to_parts', 'Access to high-value parts'),
    ],
    'R4 - Repair': [
        ('longevity_extension', 'Longevity extension'),
        ('extension_of_producer_responsibility', 'Extension of producer responsibility'),
        ('consumer_awareness', 'Consumer awareness'),
        ('potential_repair', 'Potential repair'),
        ('repairability_score', 'Repairability score'),
        ('durability_score', 'Durability score'),
        ('non_destructive_disassembly_score', 'Non-destructive disassembly score'),
        ('ease_of_reassembly', 'Ease of reassembly'),
    ],
    'R5 - Refurbish': [
        ('product_takeback', 'Product take-back'),
        ('refurbished_content', 'Refurbished content'),
        ('refurbishment_potential', 'Refurbishment rotential'),
        ('refurbishment_score', 'Refurbishment score'),
        ('upgradability_score', 'Upgradability score'),
    ],
    'R6 - Remanufacture': [
        ('product_takeback', 'Product take-back'),
        ('remanufacturing_effectiveness', 'Remanufacturing effectiveness'),
        ('consumer_awareness', 'Consumer awareness'),
        ('remanufacturing_content', 'Remanufacturing content'),
        ('remanufacturing_score', 'Remanufacturing score'),
    ],
    'R7 - Repurpose': [
        ('secondary_raw_materials', 'Secondary raw materials'),
        ('hazardous_waste_diverted', 'Hazardous waste diverted from disposal'),
        ('nonhazardous_waste_diverted', 'Non-hazardous waste diverted from disposal'),
    ],
    'R8 - Recycle': [
        ('overall_recycling_rates', 'Overall recycling rates'),
        ('recycling_rate_for_waste_streams', 'Recycling rate for waste streams'),
        ('waste_generation', 'Waste generation'),
        ('reverse_logistics', 'Reverse logistics'),
        ('recycling_potential', 'Recycling potential'),
        ('design_for_recyclability', 'Design for recyclability'),
        ('recycling_compatibility_score', 'Recycling compatibility score'),
        ('material_homogeneity_score', 'Material homogeneity score'),
        ('hazardous_substance_barrier', 'Hazardous substance barrier'),
        ('high_purity_sorting_possible', 'High purity sorting possible'),
        ('use_of_recyclable_materials', 'Use of easily recyclable materials'),
        ('recycling_collection_rate', 'Recycling collection rate'),
    ],
    'R9 - Recover': [
        ('waste_diversion_from_landfill', 'Waste diversion from landfill'),
        ('potential_recovery', 'Potential recovery'),
        ('hazardous_waste_disposal', 'Hazardous waste directed to disposal'),
        ('nonhazardous_waste_disposal', 'Non-hazardous waste directed to disposal'),
        ('energy_recoverability_benefit', 'Energy recoverability benefit'),
        ('raw_materials_input', 'Raw materials input'),
    ],
}
"""
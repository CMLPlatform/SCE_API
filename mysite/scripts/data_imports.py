"""To run this script, use `python manage.py runscript data_imports`
"""
from pathlib import Path
import pandas as pd
from django.conf import settings
# from django.contrib.auth.models import User
from dpp.models import CircularityIndicator, Instruction, ImpactIndicator, ImpactCategory
from dpp.lca import biosphere_to_dpp_flows
import logging

logger = logging.getLogger(__name__)

def csv_to_django(file_path: Path | str, Model, relations={}):
    """Read data from a CSV `file_path` into a Django `Model`."""
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

    # Bulk insert the CSV data, skipping duplicates
    objs = [Model(**row.to_dict()) for _, row in df.iterrows()]
    created = Model.objects.bulk_create(objs, ignore_conflicts=True)

    logger.info(f"{file_path.name} has been loaded as {Model.__name__} into the Django database.")
    logger.info(f"Inserted: {len(created)}, Skipped: {len(df) - len(created)}")

def run():
    circularity_csv = settings.DATA_DIR / "circularity_indicators.csv"
    csv_to_django(circularity_csv, CircularityIndicator)
    label_csv = settings.DATA_DIR / "document_labels.csv"
    csv_to_django(label_csv, Instruction)
    socioecon, _ = ImpactCategory.objects.get_or_create(name="Socio-economic impact")
    socioecon_csv = settings.DATA_DIR / "socioecon_indicators.csv"
    csv_to_django(socioecon_csv, ImpactIndicator, relations={"impact_category": socioecon.pk})
    biosphere_to_dpp_flows()

"""To run this script, use `python manage.py runscript data_imports`
"""
from pathlib import Path
import pandas as pd
from django.conf import settings
# from django.contrib.auth.models import User
from dpp.models import CircularityIndicator, Instruction, ImpactIndicator, ImpactCategory

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

def run():
    circularity_csv = settings.DATA_DIR / "circularity_indicators.csv"
    csv_to_django(circularity_csv, CircularityIndicator)
    label_csv = settings.DATA_DIR / "document_labels.csv"
    csv_to_django(label_csv, Instruction)
    socioecon, _ = ImpactCategory.objects.get_or_create(name="Socio-economic impact")
    socioecon_csv = settings.DATA_DIR / "socioecon_indicators.csv"
    csv_to_django(socioecon_csv, ImpactIndicator, relations={"impact_category": socioecon.pk})

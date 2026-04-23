import pandas as pd
import os
import csv
from django import setup as setup_django
from django.apps import apps

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
setup_django()

DATA_PATH = '../../Data/'
DPP_PATH = DATA_PATH + 'DPP_Structure.xlsx'

def analyze_models():
    results = []
    for model in apps.get_models():
        model_name = model.__name__
        fields = model._meta.local_fields
        for parent in model.__bases__:
            if parent.__name__ != 'Model':
                fields += parent._meta.local_fields
        optional = 0
        required = 0

        for field in fields:
            if field.primary_key:
                required += 1
            elif field.blank or field.null:
                optional += 1
            else:
                required += 1

        results.append({
            'Model': model_name, 'Optional': optional, 'Required': required
        })

    return results

def write_csv(results, filename=DATA_PATH + 'model_attributes.csv'):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(
            file, fieldnames=['Model', 'Optional', 'Required']
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"Results written to {filename}")

def read_excel_models(filepath='DPP_Structure.xlsx', columns=[]):
    use_sheets = [
        'Metadata', 'ProductInformation', 'DesignAndMaterials',
        'ManufacturingInformation', 'SustainabilityEvaluation', 'Circularity',
        'SustainabilityIndicators', 'CircularityIndicators',  # No attributes here
        'ServiceEvents', 'Operators',
    ]
	
    structure = pd.read_excel(filepath, sheet_name=None, dtype='str')
    data = []
    columns = columns or [
            'Class', 'Attribute', 'dataType', 'dataSchema',
            'ESPR[Optional|Mandatory]', 'Data Source', 'MCDA Applicable',
            'MCDA Datatype', 'Global?', 'Output layer',
        ]

    for sheet in structure:
        if sheet not in use_sheets:
            continue
        df = structure[sheet]
        df.columns = ['Class', 'Attribute'] + list(df.columns[2:])
        df = df[df.columns.intersection(columns)].copy()
        # Select first part of MCDA columns
        if 'MCDA Applicable' in df.columns:
            df['MCDA Applicable'] = df['MCDA Applicable'].str[0]
        if 'MCDA Datatype' in df.columns:
            df['MCDA type'] = df['MCDA Datatype'].str.split('[:, ]', n=1).str[0]
        if 'Global?' in df.columns:
            df['Global?'] = df['Global?'].str.lower()
        # Drop if Attribute is empty
        df = df.loc[df.Attribute.notna()]

        df['Sheet'] = sheet
        data.append(df)

    return pd.concat(data)

def attribute_overview():
    groups = {'Activity': 'Manufacturing', 'Alias': 'Administrative', 'BackgroundProcess': 'Manufacturing', 'CircularityEvaluation': 'Sustainability', 'CircularityIndicator': 'Sustainability', 'CircularityScore': 'Sustainability', 'CircularityTracker': 'Sustainability', 'Company': 'Manufacturing', 'Component': 'Material', 'Composition': 'Material', 'Concentration': 'Material', 'DisassemblyEvent': 'Service events', 'Document': 'Administrative', 'Document.type': 'Administrative', 'DppDetails': 'Product', 'Emission': 'Sustainability', 'EnvExchange': 'Sustainability', 'Exchange': 'Sustainability', 'Facility': 'Manufacturing', 'Flow': 'Product', 'HazardousMaterial': 'Material', 'ImpactCategory': 'Sustainability', 'ImpactIndicator': 'Sustainability', 'Importer': 'Manufacturing', 'IndicatorSet': 'Sustainability', 'InspectionEvent': 'Service events', 'Institution': 'Administrative', 'Instruction': 'Administrative', 'ItemExchange': 'Service events', 'LifeCycleEvent': 'Service events', 'MaintenanceEvent': 'Service events', 'ManufacturingProcess': 'Manufacturing', 'Material': 'Material', 'Metadata': 'Administrative', 'Organization': 'Administrative', 'Process': 'Manufacturing', 'ProductBatch': 'Product', 'ProductExchange': 'Sustainability', 'ProductItem': 'Product', 'ProductModel': 'Product', 'ProductProperties': 'Product', 'ProductionLine': 'Manufacturing', 'Publisher': 'Administrative', 'SecondaryProduct': 'Manufacturing', 'ServiceOperator': 'Service events', 'SustainabilityEvaluation': 'Sustainability', 'SustainabilityScore': 'Sustainability', 'Transport': 'Manufacturing'}
    rows = []
    for model in apps.get_models():
        model_name = model.__name__
        if model_name in ['User', 'Group', 'Session', 'Permission', 'LogEntry', 'ContentType', 'Alias']:
            continue
        # Add inherited fields (assuming a model has only 1 parent)
        fields = []
        while model.__name__ != 'Model': 
            if not model._meta.abstract:
                fields += model._meta.local_fields
            model = model.__bases__[0]

        for field in fields:
            required = True
            if not field.primary_key and (field.blank or field.null):
                required = False
            rows.append([model_name, field.name, required])
    
    att_df = pd.DataFrame(columns=['Class', 'Attribute', 'Required'], data=rows)
    # Read excel data and copy inherited rows to child classes
    excel_data = read_excel_models(DPP_PATH)
    # Replace 2 class names
    excel_data['Class'] = excel_data['Class'].replace('ManufacturingInformation', 'ProductionLine')
    excel_data['dataSchema'] = excel_data['dataSchema'].replace('ManufacturingInformation', 'ProductionLine')
    parent_mask = excel_data.Attribute=='parent'
    # inherit_list = [excel_data]
    for i, row in excel_data[parent_mask][::-1].iterrows():
        inherit = excel_data[excel_data.Class==row.dataSchema].copy()
        inherit['Class'] = row.Class
        # inherit_list.append(inherit)
        excel_data = pd.concat([excel_data, inherit])
    parent_mask = excel_data.Attribute=='parent'
    excel_data.loc[parent_mask, 'Attribute'] = (
        excel_data.loc[parent_mask, 'dataSchema'].str.lower() + '_ptr'
    )

    att_df = att_df.merge(excel_data, 'outer', sort=True)
    # Fill info for ptr and id fields
    ptr_mask = att_df.Attribute.str.endswith('_ptr')
    id_mask = (att_df.Attribute == 'id') & att_df.dataType.isna()
    fill_cols = ['dataType', 'Data Source', 'MCDA Applicable', 'Output layer']
    att_df.loc[ptr_mask, fill_cols] = ['parent', 'Auto-created', 'N', '-']
    att_df.loc[id_mask, fill_cols] = ['int', 'Auto-created', 'N', '-']

    # Add group names
    att_df['Group'] = att_df['Class'].map(groups)

    att_df.to_csv(DATA_PATH + 'DPP_Structure.csv', index=False)

    return att_df


def analyze_excel(filepath='DPP_Structure.xlsx'):
    use_sheets = [
        'Metadata', 'ProductInformation', 'DesignAndMaterials',
        'ManufacturingInformation', 'SustainabilityEvaluation', 'Circularity',
        # 'SustainabilityIndicators', 'CircularityIndicators',  # No attributes here
        'ServiceEvents', 'Operators',
    ]

    xls = pd.ExcelFile(filepath)
    all_sheets = xls.sheet_names
    mandatory_df = pd.DataFrame()
    classes = []
    outputs = []

    for sheet in all_sheets:
        if sheet not in use_sheets:
            continue
        df = pd.read_excel(filepath, sheet_name=sheet, dtype='str')
        df.columns = ['Class', 'Attribute'] + list(df.columns[2:])

        # Drop rows that shouldn't be counted
        df = df.loc[df.Attribute.notna() & (df.Attribute!='parent')]
        df = df.loc[df['Output layer'].notna()]

        # Select MCDA datapoints, also count Country links
        datapoints = df.loc[df['Output layer']!='-'].copy()
        datapoints.loc[datapoints.dataSchema=='Country', 'dataType'] = 'str'
        datapoints = datapoints.loc[~datapoints['dataType'].isin(['category', 'object'])]

        df = df.loc[~df['dataType'].isin(['category', 'option'])]

        # Count attributes by class and data source
        #TODO: assume multipliers for each Class, to calculate total fieds
        classes.append(df.pivot_table('Attribute', 'Class', 'Data Source', 'count'))
        # classes.append(df.groupby('Class')[['Attribute']].count())
        # df.pivot_table('Attribute', 'Class', ['Data Source', 'Output layer'], 'count')

        outputs.append(df.pivot_table('Attribute', 'Class', 'Output layer', 'count'))

        # Group by mandatory status and count
        mandatory = datapoints.groupby('ESPR[Optional|Mandatory]')[['Class']].count()
        mandatory_df[sheet] = mandatory['Class']

    class_df = pd.concat(classes)
    output_df = pd.concat(outputs)

    for name, data in [('mandatory', mandatory_df), ('classes', class_df), ('outputs', output_df)]:
        data.fillna(0).to_csv(f"{name}_count.csv")

def expand_hierarchy():
	columns = ['Class', 'Attribute', 'MCDA Applicable', 'MCDA Datatype', 'Global?']
	structure = read_excel_models(DPP_PATH, columns)
	# len(structure[structure['Global?'].str.contains('?', regex=False, na=False)])

	structure['Global?'] = structure['Global?'].str.strip(' ?')
	structure = structure[structure['MCDA Applicable'] == 'Y'].copy()
	structure['Attributes'] = 'All'

	mcda_file = DATA_PATH + "MCDA_hierarchy.xlsx"
	mcda_df = pd.read_excel(mcda_file)
	joined = mcda_df.merge(structure[['Class', 'Attribute', 'Attributes']], 'left')
	joined['Attribute'] = joined['Attribute'].fillna(joined['Attributes'])
	joined = joined[joined.Attribute.notna() & (joined.Attribute != 'All')]
	joined = joined.drop(columns=['Attributes'])
	joined['Attribute'] = joined['Attribute'].str.split(',\s*')
	joined = joined.explode('Attribute')

	joined = joined.merge(structure, 'left')
	
	circ_ind = mcda_df[mcda_df['Class'] == "CircularityIndicator"].copy()
	circ_ind['Class'] = circ_ind['Attributes']
	circ_ind = circ_ind.loc[:, :'Class'].merge(structure, 'left')
	joined = pd.concat([joined, circ_ind], ignore_index=True)
	
	joined = joined.drop(columns=['MCDA Applicable', 'Attributes'])
	print(joined.columns)
	joined.drop_duplicates(inplace=True)
	#for col in ['Global?', 'MCDA type', 'MCDA Datatype', 'Sheet']:
	#	joined[col] = joined[col].ffill()

	joined.to_csv(DATA_PATH + 'joined.csv', index=False)

if __name__ == '__main__':
    # results = analyze_models()
    # write_csv(results)
    result = attribute_overview()
    # analyze_excel(DPP_PATH)
    #expand_hierarchy()

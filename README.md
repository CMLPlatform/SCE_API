# Installation
To install the application on your computer, open a command line and run:
```bash
pip install sce@git+https://github.com/CMLPlatform/SCE_API.git
```

# User Manual
## Key features
This software helps you to create Digital Product Passports in a streamlined way, to comply with the EU ESPR regulations. It is designed for manufacturers of consumer goods such as clothes, electronics, and batteries.
There are two parts: a web-based interface to conveniently construct datasets, and a API module that can be used to share data with other parties.

## Recommended workflow
In the sections below, instructions are provided for using the data collector app. These instructions are ordered following the recommended workflow. It is possible to follow a different route.

## Start page
[-> Try live](http://127.0.0.1:8000/dpp/welcome)

On the start page, you find a list of recently modified production lines. A [production line](#production-line) is a sequence of [manufacturing processes](#process) that produce a consumer [product](#product). To continue working on a production line, click on its name. To create a new production line, click the green button. It is also possible to view a more detailed list of production lines, including older ones, by clicking 'See detailed list'.

## Production line
[-> Try live](http://127.0.0.1:8000/dpp/productionline/)

Creating a production line is simple: click on the button 'Add production line' when you are at the [start page](#start-page) or at the list of production lines. A [form](#forms) will be shown, which asks to enter some information about the new production line. 
- **Name\***: The asterisk indicates that the name must be specified.
- **Description**: Add a description if you want, or leave it empty.
- **Final product\***: Select the product produced by this production line. Most likely, the product doesn't exist yet, so it isn't shown in the dropdown list. Instead, click the green **+** to create a new product. 
- **Facility\***: Select the location where this production line is located. Click **+** if the [facility](#facility) is not in the list. 
To go back to the list of production lines, simply follow the link in the [navigation pane](#navigation) on the left.

When a production line is selected, the following information is shown:
- Detailed information about this production line, including a description, final product, and manufacturer.
- A depiction of [inputs and outputs](#inputs-and-outputs) of the production line, and processes contained in it.
- A list of [processes](#process). Click on one to see or edit it. Or click 'Add new process'.
- A list of [transport operations](#transport), indicating how each input or output has been transported. At first, no transport operations are specified. To create an initial set, click the green button 'Add transport operations'.

## Facility
A facility is described by 3 fields:
- **Operator\***: Select the [company](#company) that operates this production line. Click **+** if your company is not in the list. 
- **Country\***: Select the country where this facility is located.
- **Address\***: Specify the address.

Multiple production lines can refer to the same facility. The above information needs to be provided only once.

## Company
- **Name\***
- **Address**
- **Country\***
- **Contact email**: Customer support address.
- **Website**
- **Legal documents**: Attach official legal documentation associated with the company. This may include licenses, registration papers, permits, or other legally mandated certificates.
- **VAT number**

## Product
A 'product', can by any good or item that can be purchased on a market, both consumer goods and intermediate products. There are four different types of products:
- **Product model**: describes a specific model or version of a product. All items of a product model share the same design, weight, and manuals.
- **Product batch**: describes a specific batch of products, indicated by a batch number. All items of a product batch share the same supply chain (production processes).
- **Product item**: a unique product. When it is shipped, it is identical to other items from the same batch. After sales, a product item has its own history of use, repair, upgrades, etc.
- **Secondary product**: a subtype of product model, describing a product that is reused, refurbished, remanufactured, or repurposed. This is used to describe waste flows and non-virgin inputs of a [production process](process).

These four product types can be used to create DPPs with any level of detail. In case all product batches are the same, it suffices to specify the product model. When each item is unique (custom production), then a product batch is defined for each item. 

A product model or batch can be described in further detail, see [product details](#product-details).

## Product details
It is possible - and sometimes mandatory - to specify some details about a [product](#product). This can be done using two forms: **physical product properties** and **DPP details**. Physical properties are the product's weight, volumen and density. The DPP details must be specified for the (final) product for which you want to create a DPP. These DPP details are:
- **Importer**: If applicable, the legal entity that imports the product into the EU single market. Select or add the importing [Company](#company).
- **CPV code**: Common Procurement Vocabulary code.
- **GS1 GPC code**: Global Product Classification code.
- **Compliance documents\***: Attach one or more documents, according to the requirements of the product category. Select the appropriate [document type](#document).
- **Warranty period\***: Duration of the warranty, in years. Warranty conditions can be specified in a compliance document.
- **Spare parts availability duration\***: Guaranteed availability of spare parts, in years.
- **Take-back system\***: Specify which system is in place for taking back used products. Select one of the options.

## Process
Now it is time to add a production process to the production line. A process is described by:
- **Name\***
- **Production line\***: The production line that it belongs to. (Automatically filled when you use the 'Add new process' button in a [production line](production-line)).
- **Main output**: The main product produced by this process. It could be an intermediate product or a final product. It is important that each product is only produced by a single process! Even if two processes produce a similar product, you need to define a separate product for each.
- **Amount**: The number of units of the main output produced by this process. If you set the amount to '10', then you need to specify all [inputs and outputs](#inputs-and-outputs) needed to produce 10 items of the main output. 
- **Facility**: The location of this process. If you leave this empty, the location of the production line will be set.
- **Description**: Optional description.
- **Outsourced**: Check the box if the process is operated by an external company. This will be set automatically.

After adding a process, you can see the following process details:
- Inputs to process: shows a list of inputs. The symbol indicates the input type: 
	- 🧩 Component of the product
	- 🧃 Consumable
	- 🔥 Electricity or heat
	- ⚙️ Utility or equipment
	- 🧑‍🔧 Service
	- 📦 Packaging
	- ⚗️ Reactant
	- 🗑️ Waste (used as feedstock)
	- ⛏️ Natural resource extraction
- Buttons to add a new input.
- Outputs of process: Shows the main product, waste flows, and emissions.
- Buttons to add a new output.
- Detailed information about the process

To verify that all processes are connected properly, go back to the [production line](#production-line) page and check the process diagram.

## Inputs and outputs
Inputs to processes and outputs of processes all fall in the category of Exchanges. Two types of exchanges exist:
- Product exchanges: refers to inputs and outputs of man-made products and goods, including energy cariers and even services. 
- Environmental exchanges: refers to inputs of natural resources (directly extracted from the environment), and emissions of substances to the environment (e.g. to air or surface water).

A typical manufacturing process mostly has product exchanges. For instance, tap water is a product because it is produced by a water supplier. Waste flows are also product exchanges, unless the material is dumped into the environment.

However, combustion processes have many environmental exchanges, because multiple substances are emitted to the air. The most reliable way to quantify these emissions is through a chemical analysis of flue gases. Alternatively, it is possible to connect to an [average market process](#average-market-process) that describes the combustion process. These average market processes can be imported from an LCA database. Most LCA databases contain processes for common combustion activities such as power plants, boilers, and vehicles. The advantage of using these processes is that no important pollutant exchanges are omitted.

It is important to specify the type and name of the input/output. It can be an (intermediate) product produced by your company or another company. If it is unavailable from the list, you have to create the product and the process that produced it. For environmental exchanges, an extensive list of substances is available to choose from. There is no need to create new substances.

If the amount of input or output is uncertain, you can specify the uncertainty distribution. This is optional. Depending on the uncertainty type, fill the following:
- Uniform distribution (interval): minimum, maximum
- Normal distribution: mean, standard deviation
- Lognormal distribution: mean, standard deviation
- Triangular distribution: mode, minimum, maximum

The uncertainty paramters follow the conventions of [Brightway2 uncertainty data](https://deepwiki.com/maximikos/Brightway2_Intro/4.6.1-understanding-uncertainty-data).

## Average market process
An 'average market process' describes common activities, such as electricity production or the operation of a natural gas boiler. As a user, you should usually import these processes from an LCA database rather than creating them yourself. Average market processes can in turn link to products from other processes, thereby describing the whole supply chain and the associated environmental [exchanges](#inputs-and-outputs).

## Transport
Transport operations are conveniently modeled in a separate section. This way, it is not needed to create a separate transport process for each product that is used by your manufacturing process. Instead, you can directly select products purchased from suppliers as [inputs and outputs](#inputs-and-outputs).

Transport operations are always linke to a [production line](#production-line). From the detail page of a production line, you can:
- Create an initial set of transport operations
- Edit the transport details for one product
- Go to the full list of transport details

It is best to create the transport operations after all processes and exchanges have been modeled.

It is assumed that transport is only needed for products entering an leaving the production line. If transport occurs between two internal processes, you can add it manually by selecting a transport service as input. Automatically created transport entries can - and should - be edited to update the transport distance and mode of transport.

## Compositions
To see the details of a [product](#product), click on 'View' in the [process](#process) that produces it. (It will be possible later to also access from the production line page.) On this page, you can see:
- Information about the product
- Origin: the manufacturer and the production process.
- Bill of materials (BoM): list of materials in the product. This will be empty at first. Hazardous and critical materials are labeled as such.
- Components with missing BoM: supports the completion of material info, see below.

There are two ways to complete the BoM:
1. Add all the materials by clicking 'Add material' multiple times. Useful when the product consists solely of primary raw materials.
2. Go to the component(s) with missing BoM, add the composition following approach 1, go back to the original product and click 'Recalculate'.

## Publishing
After you have created the [production processes](#process), [products](#product), and their [compositions](#compositions), it is time to compile all information for a publishable DPP. The publishing page will guide you through all steps needed to validate the data, calculate sustainability scores, and register the DPP.

On the [production line page](#production-line), click the button 'Review & Publish DPP' at the bottom. Please make sure that the [facility](#facility) of the production line is specified! First of all, click the 'Edit' button to make changes to the metadata for publishing.

Next, there are five steps to go through in order:
1. Check completeness: this will check if all required information on the product is available.
2. Aggregate manufacturing process: combine all processes of the production line, such that details of individual steps are not disclosed.
3. Compute concentrations and components: calculate the concentration of hazardous and critical materials, and list the product's components.
4. Create transport table: add missing [transport](#transport) information for all the inputs that have none.
5. Do Life Cycle Assessment: LCA calculations for [environmental assessment](#sustainability-evaluation).

After running one or more steps, the status (success or failure) will be indicated. An error message explains the reason of eventual errors. You may need to make some changes before re-running failed steps.
When all five steps are completed, you can click 'Publish DPP'. This will create DPPs for the requested number of product items. **Congratulations!**

## Sustainability evaluation
A DPP describes the sustainability aspects of a product. Many sustainability indicators need to be calculated using specialized software or assessment methods. A 'Sustainability evaluation' groups all measured indicator values that were determined on a specific date or by a specific organization. 
Create a new evaluation by clicking 'Sustainability evaluations' in the [navigation panel](#navigation) and then clicking 'Add sustainability evaluation'. You are asked to enter details about the evaluation. Some of these details are LCA terminology. If you are unfamiliar with these, you can ask an environmental assessment agengy to complete the form, or search for the information in their report.
- **Product\***: Select the product model or batch that is being assessed.
- **Is environmental\***: Whether this is an environmental sustainability evaluation (LCA).
- **Functional amount\***: The quantified output of the product system used as the reference for the assessment (e.g. 1 piece of screwdriver, or 1000 sheets of paper). The unit is defined by the product selected above.
- **System boundaries**:  Defines which life cycle stages are included in the assessment, such as raw material extraction, manufacturing, distribution, use, and end-of-life. Commonly used system boundaries are 'Cradle to gate' and 'Cradle to grave'.
- **Geographical scope**: The geographic region to which the data and assumptions related to the use phase and end-of-life phase apply. Optionally select one of the following: Global, European Union, country-specific, or Other.
- **Temporal scope\***: The time period for which the data and assumptions are valid, expressed as a specific year or a range of years.
- **Impact assessment method**: The environmental impact assessment methodology used to translate manufacturing data into sustainability indicators (e.g. EF 3.0, ReCiPe, ILCD, TRACI).
- **Software used**: The software tool used to perform LCA or social impact calculations (e.g. openLCA, GaBi, SimaPro, Umberto).
- **Allocation method**: The approach used to allocate environmental impacts among co-products or multiple functions of a process. The allocation method can be mass-based, energy-based, or price-based (economic allocation).
- **Assessment date\***: The date on which the evaluation was conducted or finalized.
- **Assessed by**: Name of the organization responsible for conducting the evaluation. Create a new organization if necessary. 

## Document
In various forms, documents can be selected or uploaded. These documents contain additional information such as certificates, that cannot be stored in form fields. Documents can and should be labeled as one of the following types:
- Technical document
	- Technical drawing
	- Safety sheet
	- Conformity certificate
	- Mass balance
	- Energy balance
	- Product data sheet
- Compliance document
	- Compliance report
	- Quality certificate
	- Safety data sheet
	- Legal document
	- Labor compliance
	- Quality Management System certificate
	- Warranty information
	- Spare parts availability
	- Return and take-back
- Manual
	- User manual
	- Maintenance manual
	- Installation guide
	- End-of-life guidelines
- Label
	- Voluntary label
	- Energy label
	- Ecolabel
	- Circularity label
	- Legal markings
- Other

## Navigation
To enable easy navigation through the app, use the links provided by the navigation panel on the left:
- Production lines
- Products
- Importers #TODO 
- Sustainability evaluations
- User profile #TODO 

## Forms
The app uses forms to create new items, such as products and manufacturing processes. 
Required fields that must be filled are indicated with an asterisk, e.g. **Name\***. 
Some fields ask to link to another item, such as the operator of a process. These fields can be recognized as a drop-down box with a green plus sign (**+**) next to it. If you already created the item you wan to link to, select it in the dropdown list. Otherwise, click the **+** to create it in a pop-up window. 
After filling the form, click the 'Save' button at the bottom. In case there are any issues with the information, an error message will explain what went wrong and how to correct it. 

# API Manual
Full Digital Product Passports (DPPs) and parts of a DPP can be retrieved using the API functionality.

A DPP is uniquely identified by its registration number. It can be accessed through **www.company-website.com/api/metadata/<registration_number>**. The API response follows the basic structure of the example below. Note that, for clarity, some 'branches' are left out (indicated by `[]` and `None`).

```JSON
{
    'registration_number': '5dc50ff4-d31d-45c5-9c1e-2bc9ba830c63',
    'issuer': {'id': 1, 'legal_documents': None, 'name': 'Test Certifier AG', 'address': 'Street Name 7', 'country': 'CH', 'contact_email': '', 'website': '', 'type': 'ngo'},
    'reo': {'id': 2, 'legal_documents': None, 'name': 'Example Manufacturer GmbH', 'address': '', 'country': 'DE', 'contact_email': '', 'website': 'www.example.com', 'vat_number': 'DE812345678'},
    'product_item': {
        'id': 1,
        'product_batch': {
            'id': 2,
            'properties': None,
            'concentration': [{
                'material': {
                    'id': 2,
                    'name': 'Silver',
                    'chemical_formula': 'Ag',
                    'criticality_level': 'h',
                    'origin_country': 'ID',
                },
                'fraction': 0.1,
            }],
            'composed_of': [{'amount': 1, 'component': 2}],
            'details': {
                'compliance_documents': {
                    'manual': ['/documents/manual_EN.pdf', '/documents/manual_IT.pdf'],
                    'technical_drawing': ['/documents/design.jpg'],
                },
                'CPV_code': '',
                'GS1_GPC_code': '',
                'warranty_period': '5.0',
                'spare_parts_availability_duration': '10.0',
                'takeback_system': 'active',
                'importer': None,
            },
            'latest_sustainability_evaluation': None,
            'latest_circularity_evaluation': None,
            'model': {
                'id': 1,
                'properties': None,
                'concentration': [],
                'composed_of': [],
                'details': None,
                'latest_sustainability_evaluation': {
                    'id': 1,
                    'sustainability_score': [
                        {
                            'id': 1,
                            'impact_indicator': 1,
                            'impact_value': 9.2,
                            'upstream_phase': 0.4,
                            'manufacturing_phase': 0.3,
                            'use_phase': 0.2,
                            'end_of_life_phase': 0.1,
                            'scope_1_2_3': 7.4,
                        },
                        {
                            'id': 2,
                            'impact_indicator': 2,
                            'impact_value': 9.2,
                            'upstream_phase': 0.2,
                            'manufacturing_phase': 0.3,
                            'use_phase': 0.4,
                            'end_of_life_phase': 0.1,
                            'scope_1_2_3': 7.4,
                        },
                    ],
                    'functional_amount': 1.0,
                    'system_boundaries': 'Cradle to gate',
                    'geographical_scope': 'EU',
                    'temporal_scope': '2024',
                    'impact_assessment_method': 'EF 3.01',
                    'software_used': '',
                    'allocation_method': 'mass',
                    'assessment_date': '2026-01-01',
                    'assessed_by': 3,
                },
                'latest_circularity_evaluation': None,
                'name': 'Test Widget v2',
                'unit': 'pcs',
                'brand': '',
                'description': 'A widget with many functions',
                'unit_price': None,
                'taric_code': '01234567890128',
                'hs_code': ''
            },
            'batch_number': 202507001,
        },
        'service_events': [
            {
                'id': '782e5138-8cea-40da-86f0-692814e42206',
                'item_exchanges': [],
                'activity_data': {'name': 'Maintenance process', 'amount': 1.0, 'facility': UUID('ada17b3e-0948-44cc-be24-40fc23a7f663'), 'description': '', 'modified_at': '2026-02-24'},
                'type': 'test',
                'date': '2026-02-24',
                'operator': 3,
            },
            {
                'id': 'ea8119ca-2a11-4675-b32a-3073869b66c8',
                'item_exchanges': [{'amount': 1, 'item': 2}],
                'activity_data': {'name': 'Maintenance process', 'amount': 1.0, 'facility': UUID('ada17b3e-0948-44cc-be24-40fc23a7f663'), 'description': '', 'modified_at': '2026-02-24'},
                'type': 'corrective',
                'date': '2026-02-24',
                'operator': 3,
            }
        ],
        'serial_number': 'WGT-20250715-0042',
        'GTIN_code': '',
        'production_date': '2026-02-20',
        'circularity': 'new',
    },
    'creation_date': '2026-02-20',
    'last_modified': '2026-02-20',
    'version': '1.0',
    'language': 'DE',
    'access_link': '',
    'access_policy': '',
    'access_log_enabled': True,
    'verification_type': 0,
    'credential_format': 'xml',
    'storage_location': 0,
    'audit_trail_mechanism': 0,
    'update_interval': 'A',
}
```

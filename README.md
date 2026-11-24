# Installation
The app is a Django project; it is not installed as a package. With Python 3.12:

```bash
git clone https://github.com/CMLPlatform/SCE_API.git
cd SCE_API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or requirements-dev.txt to also run the tests
cp .env.example .env                     # then set DJANGO_DEBUG=True for local development
cd mysite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver               # http://127.0.0.1:8000/
```

Reference data (circularity indicators, document labels, socio-economic indicators and the emissions of the LCA database) is loaded with `python manage.py runscript data_imports`. The emissions need the Brightway project, which is created on first use.

`requirements.txt` pins the versions the tests pass with. To upgrade a package, change its version, run the tests, then commit.

## Running the tests
```bash
pip install -r requirements-dev.txt
cd mysite
DJANGO_SECRET_KEY=test python manage.py test api dpp accounts
DJANGO_SECRET_KEY=test DJANGO_SETTINGS_MODULE=mysite.settings pytest dss/tests.py
```
The same commands run in GitHub Actions on every push.

# Configuration
Settings that differ per computer or server (secret key, debug mode, host names, database) are read from environment variables or from a `.env` file in the repository root. Copy `.env.example` to `.env` and fill it in. For local development, setting `DJANGO_DEBUG=True` is enough; on a server, always set `DJANGO_SECRET_KEY` and keep `DJANGO_DEBUG=False`.

## Access rules
- The web interface requires login, except the welcome page and published DPPs (`/dpp/final/<uuid>/`).
- Production lines, and their processes, exchanges, transport entries and publishing steps, are only visible to the user who created the production line (and to staff). Companies, materials, products and background processes are shared between all logged-in users.
- The REST API (`/api/`) requires login. Published DPPs (`/api/metadata/`) can be read by anyone; only staff can change them.
- The Decision Support System API (`/dss/`) does not require login, so other tools can call it, but anonymous calls are rate-limited. Sessions are identified by a random ID (UUID), returned as `session_id`.

## Demo data
For testing and demonstrations, load a synthetic example of the battery cooling plate use case:

```bash
python manage.py seed_demo                  # load once; prints the password of user 'demo'
python manage.py seed_demo --reset          # remove and load again
python manage.py seed_demo --remove         # remove the demo data
```

It creates a manufacturer, a supplier, materials, products, a production line with three processes (degreasing, dynamic beam laser welding, leak test), transport, DPP details, publishing settings with steps 1 to 4 done, one published DPP, a sustainability evaluation and two decision-support sessions. Example requests in the format the L4M platform sends are in `mysite/dss/examples/` (see the README there), and the test page `/dss/kam-input/` lets you send a key account manager request from the browser, pre-filled with the same example. All names and numbers are invented; they are not measurements or real company data.

## Front end
The pages are server-rendered Django templates styled with [Bootstrap 5](https://getbootstrap.com/), following the look of the Lasers4MaaS platform. Everything the pages need is served by the app itself, so no page loads files from an outside server:

| What | Where |
| --- | --- |
| Bootstrap 5.3 (CSS and JS) and Bootstrap Icons | `mysite/dpp/static/vendor/bootstrap/`, `.../bootstrap-icons/` |
| Fonts: Roboto (app) and Outfit (landing page), latin subsets | `mysite/dpp/static/vendor/fonts/` |
| Mermaid, for the production line flowchart | `mysite/dpp/static/vendor/mermaid/` |
| App theme (colours, sidebar, tables, wizard) | `mysite/dpp/static/css/sce.css` |
| Small shared scripts (table search, clickable rows, tabs) | `mysite/dpp/static/js/sce.js` |
| Landing page styles | `mysite/dpp/static/css/landing.css` |

Page layouts, in `mysite/templates/`:
- `base.html`: the app layout with the sidebar; all app pages extend it (also through `dpp/base.html`).
- `auth_base.html`: log in, sign up and password reset.
- `public_base.html`: the public DPP page, without the sidebar.
- `landing.html`: the public landing page at `/`.

Forms are rendered with `crispy-bootstrap5`. To update a stored library, download the new version (for example with `npm pack bootstrap`), replace the files in `static/vendor/`, and check the pages.

# User Manual
## Key features
This software helps you to create Digital Product Passports in a streamlined way, to comply with the EU ESPR regulations. It is designed for manufacturers of consumer goods such as clothes, electronics, and batteries.
There are two parts: a web-based interface to conveniently construct datasets, and a API module that can be used to share data with other parties.

## Recommended workflow
In the sections below, instructions are provided for using the data collector app. These instructions are ordered following the recommended workflow. It is possible to follow a different route.

## Start page
[-> Try live](http://127.0.0.1:8000/dpp/welcome)

The public landing page at `/` explains the tool; after logging in you arrive at the start page (Home in the sidebar). There you find a list of recently changed production lines. A [production line](#production-line) is a sequence of [manufacturing processes](#process) that produce a consumer [product](#product). To continue working on a production line, click its row. To create a new production line, click 'New production line' at the top right. For the full list, click 'All production lines' or Production lines in the sidebar.

## Production line
[-> Try live](http://127.0.0.1:8000/dpp/productionline/)

Creating a production line is simple: click 'New production line' on the [start page](#start-page), or 'Add production line' on the list of production lines. A [form](#forms) will be shown, which asks to enter some information about the new production line. 
- **Name\***: The asterisk indicates that the name must be specified.
- **Description**: Add a description if you want, or leave it empty.
- **Final product\***: Select the product produced by this production line. Most likely, the product doesn't exist yet, so it isn't shown in the dropdown list. Instead, click the **+** next to the list to create a new product. 
- **Facility\***: Select the location where this production line is located. Click **+** if the [facility](#facility) is not in the list. 
To go back to the list of production lines, use the breadcrumb at the top of the page or Production lines in the [sidebar](#navigation).

The page of a production line has four tabs:
- **Overview**: a flowchart of the [inputs and outputs](#inputs-and-outputs) and the processes of the production line, and its details (description, final product, facility).
- **Processes**: the list of [processes](#process), with a search box. Click a row to see or edit a process, or click 'Add process'.
- **Transport**: the [transport operations](#transport), showing how each input or output is transported. At first there are none; click 'Add transport operations' to create an initial set.
- **Publish DPP**: the status of [publishing](#publishing), and the button to start or continue it.

The buttons at the top right add a process, or start or continue publishing.

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
- **Production line\***: The production line that it belongs to. (Automatically filled when you use the 'Add process' button of a [production line](#production-line)).
- **Main output**: The main product produced by this process. It could be an intermediate product or a final product. It is important that each product is only produced by a single process! Even if two processes produce a similar product, you need to define a separate product for each.
- **Amount**: The number of units of the main output produced by this process. If you set the amount to '10', then you need to specify all [inputs and outputs](#inputs-and-outputs) needed to produce 10 items of the main output. 
- **Facility**: The location of this process. If you leave this empty, the location of the production line will be set.
- **Description**: Optional description.
- **Outsourced**: Check the box if the process is operated by an external company. This will be set automatically.

After adding a process, its page shows:
- **Inputs**: a table of the inputs, with a label for the type of each: component of the product, consumable, electricity or heat, utility or equipment, service, packaging, reactant, waste (used as feedstock) or resource extraction. Click an amount to edit an input, or × to remove it. The buttons below the table add an input, packaging or a resource extraction.
- **Outputs**: the main product, waste flows and emissions, with buttons to add waste or an emission. 'View' opens the main product.
- **Details**: the details of the process. Edit or delete the process with the buttons at the top right.

To verify that all processes are connected properly, go back to the [production line](#production-line) page and check the flowchart on the Overview tab.

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
To see the details of a [product](#product), click 'View' next to the main product of the [process](#process) that produces it, or open it from Products in the sidebar. The product page has three tabs:
- **Product details**: information about the product, its origin (the manufacturer and the production process) and its physical properties.
- **Composition**: the bill of materials (BoM), the list of materials in the product. It is empty at first. Hazardous and critical materials are labelled as such. Next to it, the components that have no BoM yet, see below.
- **DPP details**: the [product details](#product-details) needed for the passport.

There are two ways to complete the BoM:
1. Add all the materials by clicking 'Add material' multiple times. Useful when the product consists solely of primary raw materials.
2. Go to the component(s) with missing BoM, add the composition following approach 1, go back to the original product and click 'Recalculate from components'.

## Publishing
After you have created the [production processes](#process), [products](#product), and their [compositions](#compositions), it is time to compile all information for a publishable DPP. The publishing page will guide you through all steps needed to validate the data, calculate sustainability scores, and register the DPP.

On the [production line page](#production-line), click 'Review & publish DPP' at the top right (or on the Publish DPP tab). Please make sure that the [facility](#facility) of the production line is specified! First, click 'Edit publishing details' to fill in the metadata for publishing.

Next, there are five steps to go through in order. Click 'Run all steps', or 'Run from here' next to a step:
1. Check completeness: this will check if all required information on the product is available.
2. Aggregate manufacturing process: combine all processes of the production line, such that details of individual steps are not disclosed.
3. Compute concentrations and components: calculate the concentration of hazardous and critical materials, and list the product's components.
4. Create transport table: add missing [transport](#transport) information for all the inputs that have none.
5. Do Life Cycle Assessment: LCA calculations for [environmental assessment](#sustainability-evaluation).

Each step shows its status: Done, Failed or Pending. If a step fails, a message at the top explains why. You may need to make some changes before running the failed step again.
When all five steps are done, a 'Publish' button appears at the top right. It creates DPPs for the requested number of product items. **Congratulations!** Each published DPP has a public page at `/dpp/final/<registration number>/`.

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
The sidebar on the left (behind the menu button on a phone) links to:
- Home, Production lines, Products, Sustainability evaluations and Published DPPs;
- under **Libraries**: Materials, Companies, Facilities, Importers, Emissions and Documents;
- at the bottom: Settings (your profile and password) and Log out.

The breadcrumb at the top of each page leads back to the pages above it. Lists have a search box that filters the rows on the page.

## Forms
The app uses forms to create new items, such as products and manufacturing processes. 
Required fields that must be filled are indicated with an asterisk, e.g. **Name\***. 
Some fields ask to link to another item, such as the operator of a process. These fields can be recognized as a drop-down box with a plus sign (**+**) next to it. If you already created the item you want to link to, select it in the dropdown list. Otherwise, click the **+** to create it in a pop-up window. 
After filling the form, click 'Create' (or 'Save changes') at the bottom. In case there are any issues with the information, an error message will explain what went wrong and how to correct it. 

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

# Decision Support System manual
The Sustainability and Cost Module features a Decision Support System (DSS) that can be accessed through an API. It is specifically designed for supporting decisions in laser welding. The DSS has a user interface to guide you through the process of setting decision preferences, in four steps: KPI selection (including any missing KPI values), analysis setup, weights and thresholds, and sampling and ranking. The results page shows the ranking in charts and tables.

| Endpoint | Role | Returns |
| --- | --- | --- |
| `POST /dss/experiment/` | Process developer | The KPIs of one experiment |
| `POST /dss/experiments/` | Process developer | A redirect to the wizard for comparing the experiments |
| `POST /dss/welding-station/` | Key account manager | The KPIs of one welding station |
| `POST /dss/welding-stations/` | Key account manager | `{"session_id": ...}`; the wizard is at `/dss/<session_id>/step/0/` |
| `POST /dss/calculate/` | Any | The MCDA ranking for a decision matrix and settings |

The full API description is at `/schema/swagger/`. Example requests for each endpoint are in `mysite/dss/examples/`.

## API access
To receive decision support for comparing different laser welding parameters, send a post request to [main-domain.com/dss/experiments/]. The request should contain a list of experiments with the following structure:
```JSON
[
  {
    "experimentId": 12,
    "weldLength": 29,
    "weldSpeed": 100,
    "country": "DE",
    "laserPowerkW": 4,
    "weldingStationPowerkW": 12,
    "consumables": [
      {
        "name": "Nitrogen",
        "flowRate": 15.2,
        "unit": "m3/h"
      },
      {
        "name": "Argon",
        "flowRate": 6,
        "unit": "m3/h"
      },
      {
        "name": "Aluminium (filler wire)",
        "flowRate": 0.02,
        "unit": "kg/h"
      }
    ],
    "qualityParameters": [
      {
        "name": "Porosity",
        "value": 3.2,
        "target": "min"
      },
      {
        "name": "Tensile strength",
        "value": 0.18,
        "target": "max"
      },
      {
        "name": "Weld depth",
        "value": 3,
        "target": 3.5
      }
    ]
  }
]
```


## Criteria calculations

Calculations for deriving the KPIs used as decision criteria in the DSS, for the Process Developer. These calculations are implemented in the function `calculate_experiment_kpis`, in `mysite/dss/views.py`.
- Amount of shielding gas = gas flow rate × processing time
- Amount of filler wire = filler wire use rate × processing time
- Consumables costs = Σ amount × price (for all consumables)
- Labour costs = processing time × 3 × wages (in the specific country)
- Process energy use = processing time × (laser power + welding station power)
- Energy costs = process energy use × electricity price (in the specific country)
- Operating costs = consumables costs + labour costs + energy costs
- Consumables footprint = Σ amount × material carbon footprint (for all consumables)
- Process carbon footprint = consumables footprint + process energy use × electricity footprint (in the specific country)
- The technical quality indicators are directly used without calculations.

Calculations for deriving KPIs for the Key Account Manager, in the same function. Processing time = weld length / weld speed; cycle time is given in the request.
- Amount of shielding gas = gas flow rate × processing time
- Amount of filler wire = filler wire use rate × processing time
- Consumables costs = Σ amount × price (for all consumables)
- Labour costs = cycle time × 3 × wages (in the specific country)
- Process energy use = processing time × laser power + cycle time × welding station power
- Energy costs = process energy use × electricity price (in the specific country)
- Annual production = 240 days/year × 16 hours/day × 3600 seconds/hour / cycle time
- Operating costs = consumables costs + labour costs + energy costs + maintenance costs / annual production
- Materials costs = Σ material weight × material price (for all parts)
- Investment costs (CAPEX) = 5,860,000 / 3 € (fixed value in the code)
- Service life = 15 years (fixed value)
- Amortized CAPEX = investment costs / (service life × annual production)
- Total production costs = (operating costs + materials costs + amortized CAPEX) / (1 – scrap rate)
- Consumables footprint = Σ amount × material carbon footprint (for all consumables)
- Process carbon footprint = consumables footprint + process energy use × electricity footprint (in the specific country)
- Materials footprint = Σ material weight × material carbon footprint (for all parts)
- Product carbon footprint = (process carbon footprint + materials footprint) / (1 – scrap rate)
- The remaining KPIs are directly used without calculations: recyclability, process monitoring, process automation level, operator specialization level, production lead time, machine saturation, technical quality indicators.

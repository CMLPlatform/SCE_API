# User Manual
## Key features
This software helps you to create Digital Product Passports in a streamlined way, to comply with the EU ESPR regulations. It is designed for manufacturers of consumer goods such as clothes, electronics, and batteries.
There are two parts: a web-based interface to conveniently construct datasets, and a API module that can be used to share data with other parties.

## Recommended workflow
In the sections below, instructions are provided for using the data collector app. These instructions are ordered following the recommended workflow. It is possible to follow a different route.

## [Start page](http://127.0.0.1:8000/dpp/welcome)
On the start page, you find a list of recently modified production lines. A [production line] is a sequence of [manufacturing processes](#process) that produce a [consumer product]. To continue working on a production line, click on its name. To create a new production line, click the green button. It is also possible to view a more detailed list of production lines, including older ones, by clicking 'See detailed list'.

## [Production line](#http://127.0.0.1:8000/dpp/productionline/)
Creating a production line is simple: click on the button 'Add production line' when you are at the [start page](#start page) or at the list of production lines. A [form](#forms) will be shown, which asks to enter some information about the new production line. 
- **Name\***: The asterisk indicates that the name must be specified.
- **Description**: Add a description if you want, or leave it empty.
- **Final product\***: Select the product produced by this production line. Most likely, the product doesn't exist yet, so it isn't shown in the dropdown list. Instead, click the green **+** to create a new product. 
- **Producing company\***: Select the company that operates this production line. Click **+** if your company is not in the list. 
To go back to the list of production lines, simply follow the link in the [navigation pane](#navigation) on the left.

When a production line is selected, the following information is shown:
- Detailed information about this production line, including a description, final product, and manufacturer.
- A depiction of [inputs and outputs](#inputs and outputs) of the production line, and processes contained in it.
- A list of [processes](#process). Click on one to see or edit it. Or click 'Add new process'.
- A list of [transport operations](#transport), indicating how each input or output has been transported. At first, no transport operations are specified. To create an initial set, click the green button 'Add transport operations'.

## Products
With 'products', we refer to all goods and items that can be purchased on a market, both consumer goods and intermediate products. There are four different types of products:
- Product model: describes a specific model or version of a product. All items of a product model share the same design, weight, and manuals.
- Product batch: describes a specific batch of products, indicated by a batch number. All items of a product batch share the same supply chain (production processes).
- Product item: a unique product. When it is shipped, it is identical to other items from the same batch. After sales, a product item has its own history of use, repair, upgrades, etc.
- Secondary product: a subtype of product model, describing a product that is reused, refurbished, remanufactured, or repurposed. This is used to describe waste flows and non-virgin inputs of a [production process](process).

These three product types can be used to create DPPs with any level of detail. In case all product batches are the same, it suffices to specify the product model. When each item is unique (custom production), then a product batch is defined for each item. 

A product model or batch can be described in further detail in the form of **physical product properties** and **DPP details**. The DPP details must be specified for the (final) product for which you want to create a DPP.
## Process
Now it is time to add a production process to the production line. A process is described by:
- Name: Process name.
- Production line: The production line that it belongs to.
- Main output: The main product produced by this process. It could be an intermediate product or a final product. It is important that each product is only produced by a single process! Even if two processes produce a similar product, you need to define a separate product for each.
- Amount: The number of units of the main output produced by this process. If you set the amount to '10', then you need to specify all [inputs and outputs](#Inputs and outputs) needed to produce 10 items of the main output. 
- Producing company: The manufacturer responsible for this process. If you leave this empty, the operator of the production line will be set as producing company.
- Location: Country where the process takes place.
- Description: Optional description.
- Outsourced: Check the box if the process is operated by an external company. This will be set automatically.

After adding a process, you can see the following process details:
- Inputs to process: shows a list of inputs. #TODO The symbol indicates the input type: consumable, intermediate product or component, energy, natural resource, or .... #TODO resource extraction is shown as output.
- Buttons to add a new input.
- Outputs of process: Shows the main product, waste flows, and emissions.
- Buttons to add a new output.
- Detailed information about the process

## Inputs and outputs
Inputs to processes and outputs of processes all fall in the category of Exchanges. Two types of exchanges exist:
- Product exchanges: refers to inputs and outputs of man-made products and goods, including energy cariers and even services. 
- Environmental exchanges: refers to inputs of natural resources (directly extracted from the environment), and emissions of substances to the environment (e.g. to air or surface water).
A typical manufacturing process mostly has product exchanges. For instance, tap water is a product because it is produced by a water supplier. Waste flows are also product exchanges, unless the material is dumped into the environment.  
However, combustion processes have many environmental exchanges, because multiple substances are emitted to the air. The most reliable way to quantify these emissions is through a chemical analysis of flue gases. Alternatively, it is possible to connect to an [average market process](#average market process) that describes the combustion process. These average market processes can be imported from an LCA database. Most LCA databases contain processes for common combution activities such as power plants, boilers, and vehicles. The advantage of using these processes is that no important pollutant exchanges are omitted.

## Average market process
An 'average market process' describes common activities, such as electricity production or the operation of a natural gas boiler. As a user, you should usually import these processes from an LCA database rather than creating them yourself. Average market processes can in turn link to products from other processes, thereby describing the whole supply chain and the associated environmental [exchanges](#Inputs and outputs).

## Transport
Transport operations are conveniently modeled in a separate section. This way, it is not needed to create a separate transport process for each product that is used by your manufacturing process. Instead, you can directly connect your [process](#process) to products purchased from suppliers.

Transport operations are always linke to a [production line](#production line). From the detail page of a production line, you can:
- Create an initial set of transport operations
- Edit the transport details for one product
- Go to the full list of transport details

It is best to create the transport operations after all processes and exchanges have been modeled.

It is assumed that transport is only needed for products entering an leaving the production line. If transport occurs between two internal processes, you can add it. Automatically created transport entries can - and should - be edited to update the transport distance and mode of transport.

## Sustainability evaluation
A DPP describes the sustainability aspects of a product. Many sustainability indicators need to be calculated using specialized software or assessment methods. A 'Sustainability evaluation' groups all measured indicator values that were determined on a specific date or by a specific organization. 
Create a new evaluation by clicking 'Sustainability evaluations' in the [navigation panel](#navigation) and then clicking 'Add sustainability evaluation'. You are asked to enter details about the evaluation. Some of these details are LCA terminology. If you are unfamiliar with these, you can ask an environmental assessment agengy to complete the form, or search for the information in their report.
- **Product\***: Select the product model or batch that is being assessed.
- **Functional amount\***: The quantified output of the product system used as the reference for the assessment (e.g. 1 piece of screwdriver, or 1000 sheets of paper). The unit is defined by the product selected above.
- **System boundaries**:  Defines which life cycle stages are included in the assessment, such as raw material extraction, manufacturing, distribution, use, and end-of-life. Commonly used system boundaries are 'Cradle to gate' and 'Cradle to grave'.
- **Geographical scope**: The geographic region to which the data and assumptions related to the use phase and end-of-life phase apply. Optionally select one of the following: Global, European Union, country-specific, or Other.
- **Temporal scope\***: The time period for which the data and assumptions are valid, expressed as a specific year or a range of years.
- **Impact assessment method**: The environmental impact assessment methodology used to translate manufacturing data into sustainability indicators (e.g. EF 3.0, ReCiPe, ILCD, TRACI).
- **Software used**: The software tool used to perform LCA or social impact calculations (e.g. openLCA, GaBi, SimaPro, Umberto).
- **Allocation method**: The approach used to allocate environmental impacts among co-products or multiple functions of a process. The allocation method can be mass-based, energy-based, or price-based (economic allocation).
- **Assessment date\***: The date on which the evaluation was conducted or finalized.
- **Assessed by**: Name of the organization responsible for conducting the evaluation. Create a new organization if necessary. 

## Navigation
To enable easy navigation through the app, use the links provided by the navigation panel on the left:
- Production lines
- Products
- Importers #TODO 
- Sustainability evaluations
- Profile #TODO 
## Forms
The app uses forms to create new items, such as products and manufacturing processes. 
Required fields that must be filled are indicated with an asterisk, e.g. **Name\***. 
Some fields ask to link to another item, such as the operator of a process. These fields can be recognized as a drop-down box with a green plus sign (**+**) next to it. If you already created the item you wan to link to, select it in the dropdown list. Otherwise, click the **+** to create it in a pop-up window. 
After filling the form, click the 'Save' button at the bottom. In case there are any issues with the information, an error message will explain what went wrong and how to correct it. 
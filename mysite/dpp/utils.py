from dpp.models import SustainabilityScore, CircularityScore
from api.serializers import CompanySerializer, OrganizationSerializer, ProductBatchSerializer, ProductModelSerializer, HazardousMaterialSerializer, MaterialSerializer, ProductPropertiesSerializer, DppDetailsSerializer, FacilitySerializer, ProductExchangeSerializer, EnvExchangeSerializer

def safe(func):
    """Safely call `func` (any database query), ignoring errors.
    """
    try:
        return func()
    except Exception:
        return ''

def verbose_choice_value(object, field_name, value=None):
    """Return the display label for a field with `choices`, or the raw value if not applicable.
    """
    try:
        if value==None:
            value = getattr(object, field_name)
        field = object._meta.get_field(field_name)
        return dict(field.choices).get(value, value) if field.choices else value
    except Exception:
        return value

def prepare_dict(data, Model=None):
    if isinstance(data, list):
        return {
            str(i + 1): prepare_dict(item, Model)
            for i, item in enumerate(data)
        }
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Get verbose name for the key
            if Model is not None:
                try: # Take the verbose_name if available
                    field = Model._meta.get_field(key)
                    verbose_key = field.verbose_name.title()
                except Exception:
                    verbose_key = key.replace('_', ' ').title()
                value = verbose_choice_value(Model, key, value)
            else:
                verbose_key = key.replace('_', ' ').title()
            result[verbose_key] = prepare_dict(value, Model)
        return result
    return data
  
def dpp_as_dict(dpp):
    """Serialize all DPP info to a nested dictionary.
    'N/A' indicates missing or NULL values.
    """
    product_model = dpp.product_item.product_batch.model

    D = {
        "Metadata": {
            "Data governance": {
                "Access log enabled":       safe(lambda: dpp.access_log_enabled),
                "Verification type":        safe(lambda: dpp.verification_type),
                "Credential format":        safe(lambda: dpp.credential_format),
                "Storage location":         safe(lambda: dpp.storage_location),
                "Audit trail mechanism":    safe(lambda: dpp.audit_trail_mechanism),
                "Update interval":          safe(lambda: dpp.update_interval),
                "Access policy":            safe(lambda: dpp.access_policy),
            },
            "Traceability": {
                "Registration number":      safe(lambda: dpp.registration_number),
                "Version":                  safe(lambda: dpp.version),
                "Creation date":            safe(lambda: dpp.creation_date),
                "Access link":              safe(lambda: dpp.access_link),
                "Language":                 safe(lambda: dpp.language),
                "Responsible Economic Operator": prepare_dict(CompanySerializer(dpp.reo).data, dpp.reo),
                "Issuer": prepare_dict(OrganizationSerializer(dpp.issuer).data, dpp.issuer),
            },
        },
        "Product information": {
            "Product identification": {
                "Serial number": dpp.product_item.serial_number,
                "Production date": dpp.product_item.production_date,
                "Circularity": dpp.product_item.circularity,
                "Batch": prepare_dict(
                    ProductBatchSerializer(dpp.product_item.product_batch).data, dpp.product_item.product_batch
                ),
                "Model": safe(lambda: prepare_dict(
                    ProductModelSerializer(dpp.product_item.product_batch.model).data, dpp.product_item.product_batch.model
                )),
            },
            "Design and materials": {
                "Bill of materials": safe(lambda: [
                    {
                        "Component": entry.component.name,
                        "Amount": entry.component.amount,
                    }
                    for entry in dpp.product_item.product_batch.model.composed_of.all()
                ]),
                "Hazardous materials": safe(lambda: [
                    {
                        "Fraction": entry.fraction,
                        "Material": prepare_dict(
                            HazardousMaterialSerializer(entry.material).data, entry.material
                        ),
                    }
                    for entry in dpp.product_item.product_batch.model.concentration.all() #FIXME: filter
                ]),
                "Critical materials": safe(lambda: [
                    {
                        "Fraction": entry.fraction,
                        "Criticality level": safe(lambda e=entry: e.material.criticality_level),
                    }
                    for entry in dpp.product_item.product_batch.model.concentration.filter(
                        material__criticality_level__isnull=False
                    )
                ]),
                "Packaging info": safe(lambda: [
                    {
                        "Fraction": entry.fraction,
                        "Material": prepare_dict(
                            MaterialSerializer(entry.material).data, entry.material
                        ),
                    }
                    for entry in dpp.product_item.product_batch.model.concentration.filter(
                        material__name='Total packaging material'
                    )
                ]),
                "Material properties": safe(lambda: [
                    {
                        "Fraction": entry.fraction,
                        "Material": prepare_dict(
                            MaterialSerializer(entry.material).data, entry.material
                        ),
                    }
                    for entry in dpp.product_item.product_batch.model.concentration.exclude(
                        material__name='Total packaging material'
                    )
                ]),
                "Physical properties": safe(lambda: prepare_dict(
                    ProductPropertiesSerializer(dpp.product_item.product_batch.model.properties).data,
                    dpp.product_item.product_batch.model.properties
                )),
            },
            "Compliance": {
                "Info": safe(lambda: prepare_dict(
                    DppDetailsSerializer(dpp.product_item.product_batch.model.details).data,
                    dpp.product_item.product_batch.model.details
                )),
                "Compliance documents": safe(lambda: {
                    doc_type: [
                        doc.file.name
                        for doc in dpp.product_item.product_batch.model.details.compliance_documents.filter(type=doc_type)
                    ]
                    for doc_type in dpp.product_item.product_batch.model.details.compliance_documents
                        .values_list('type', flat=True).distinct()
                }),
            },
        },
        "Manufacturing information": {
            "Manufacturing process": {
                "Name": verbose_choice_value(dpp.product_item.product_batch.model.manufacturing_info, 'name'),
                "Description": verbose_choice_value(dpp.product_item.product_batch.model.manufacturing_info, 'description'),
                "Last updated": verbose_choice_value(dpp.product_item.product_batch.model.manufacturing_info, 'modified_at'),
                "Facility": safe(lambda: prepare_dict(
                    FacilitySerializer(dpp.product_item.product_batch.model.manufacturing_info.facility).data,
                    dpp.product_item.product_batch.model.manufacturing_info.facility
                )),
                "Product exchanges": safe(lambda: [
                    prepare_dict(ProductExchangeSerializer(pe).data, pe)
                    for pe in dpp.product_item.product_batch.model.manufacturing_info.prod_exchanges.all()
                ]),
                "Environmental exchanges": safe(lambda: [
                    prepare_dict(EnvExchangeSerializer(ee).data, ee)
                    for ee in dpp.product_item.product_batch.model.manufacturing_info.env_exchanges.all()
                ]),
            },
        },
        "Sustainability": {
            "Socio-economic sustainability": {},
            "Environmental impacts": {},
            "Circularity": {},
        }
    }

    latest_socioecon_ass = product_model.sustainability_evaluation.filter(is_environmental=False).order_by("-assessment_date").first()
    if latest_socioecon_ass:
        D["Sustainability"]["Socio-economic sustainability"] = {
            "Assessment information": {
                "Geographical scope": latest_socioecon_ass.geographical_scope,
                "Temporal_scope": latest_socioecon_ass.temporal_scope,
                "Assessment date": latest_socioecon_ass.assessment_date,
                "Assessed by": latest_socioecon_ass.assessed_by,
            },
            "childEmployment": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="childEmployment").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "forceLabourFrequency": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="forceLabourFrequency").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "minimumWage": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="minimumWage").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "nonFatalAccidentsRate": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="nonFatalAccidentsRate").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "fatalAccidentsRate": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="fatalAccidentsRate").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "rightOfAssociation": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="rightOfAssociation").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "genderWageGap": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="genderWageGap").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "economicDevContribution": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="economicDevContribution").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "valueAdded": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="valueAdded").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
            "employment": SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=False, impact_indicator__method="employment").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first(),
        }
    
    latest_environ_ass = product_model.sustainability_evaluation.filter(is_environmental=True).order_by("-assessment_date").first()
    if latest_environ_ass:
        D["Sustainability"]["Environmental impacts"] = {
            "Assessment information": {
                "Geographical scope": latest_environ_ass.geographical_scope,
                "Temporal_scope": latest_environ_ass.temporal_scope,
                "Assessment date": latest_environ_ass.assessment_date,
                "Assessed by": latest_environ_ass.assessed_by,
            },
            "Acidification": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="Acidification").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "ClimateChange": {
                "ClimateChangebiogenic": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="ClimateChangebiogenic").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "ClimateChangefossil": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="ClimateChangefossil").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "ClimateChangelandUseAndLandUseChange": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="ClimateChangelandUseAndLandUseChange").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "AquaticEcoToxicity": {
                "AquaticEcoToxicity": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EcotoxicityFreshwater").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "EcotoxicityFreshwaterInorganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EcotoxicityFreshwaterInorganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "EcotoxicityFreshwaterOrganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EcotoxicityFreshwaterOrganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "RespiratoryInorganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EfparticulateMatter").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "Eutrophication": {
                "EutrophicationMarine": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EutrophicationMarine").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "EutrophicationFreshwater": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EutrophicationFreshwater").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "TerrestrialEutrophication": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="EutrophicationTerrestrial").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "CancerHumanHealtEffects": {
                "HumanToxicityCancer": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityCancer").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "HumanToxicityCancerInorganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityCancerInorganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "HumanToxicityCancerOrganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityCancerOrganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "NonCancerHumanHealtEffects": {
                "HumanToxicityNoncancer": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityNoncancer").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "HumanToxicityNoncancerInorganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityNoncancerInorganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "HumanToxicityNoncancerOrganics": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="HumanToxicityNoncancerOrganics").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "IonizingRadiation": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="IonisingRadiationHumanHealth").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "LandUse": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="LandUse").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "OzoneDepletion": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="OzoneDepletion").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "PhotochemicalOzoneCreation": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="PhotochemicalOzoneFormationHumanHealth").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            "AbioticResourceDepletion": {
                "AbioticResourceDepletion": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="ResourceUseFossils").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
                "AbioticResourceDepletion": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="ResourceUseMineralsAndMetals").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
            },
            "Other": safe(SustainabilityScore.objects.filter(evaluation__product=product_model, evaluation__is_environmental=True, impact_indicator__method="WaterUse").order_by("-evaluation__assessment_date").values_list("impact_value", flat=True).first()),
        }
    
    latest_circularity_ass = product_model.circularity_evaluation.order_by("-assessment_date").first()
    if latest_circularity_ass:
        D["Sustainability"]["Circularity"] = {
            "Assessment information": {
                "Assessment date": latest_circularity_ass.assessment_date,
                "Assessed by": latest_circularity_ass.assessed_by,
            },
            "R0: Refuse": {
                "Refuse (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refuse hazardous substances": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refuse fossil energy use": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refuse non-renewable materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refuse other materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Avoided product consumption": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R0.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R1: Rethink": {
                "Rethink (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Modularity": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Product take-back": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Critical Materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Shared use": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Durability": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Potential use during lifetime": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Multifunctionality": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.07").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Modularity score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.08").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.09").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Number of components": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.10").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Material composition complexity": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.11").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Number of tools required": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.12").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Separable pieces ratio": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R1.13").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R2: Reduce": {
                "Reduce (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Raw materials intensity reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Energy intensity reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Energy consumption reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Waste generation reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Material losses reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Water intensity reduction": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Water consumption": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R2.07").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R3: Reuse": {
                "Reuse (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Reuse rate": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Product take-back": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Consumer awareness": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Potential use": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Ownership time": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Voidance of reuse barriers": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Reuse potential": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.07").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Costs of reuse": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.08").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Access to high-value parts": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R3.09").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R4: Repair": {
                "Repair (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Longevity extension": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Extension of producer responsibility": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Consumer awareness": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Potential repair": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Repairability score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Durability score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Non-destructive disassembly score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.07").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Ease of reassembly": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R4.08").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R5: Refurbish": {
                "Refurbish (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Product take-back": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refurbished content": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refurbishment potential": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Refurbishment score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Upgradability score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R5.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R6: Remanufacture": {
                "Remanufacture (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Product take-back": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Remanufacturing effectiveness": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Consumer awareness": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Remanufacturing content": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Remanufacturing score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R6.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R7: Repurpose": {
                "Repurpose (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R7").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Secondary raw materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R7.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Hazardous waste diverted from disposal": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R7.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Non-hazardous waste diverted from disposal": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R7.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R8: Recycle": {
                "Recycle (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Overall recycling rates": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Recycling rate for waste streams": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Waste generation": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Reverse logistics": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Recycling potential": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Design for recyclability": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Recycling compatibility score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.07").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Material homogeneity score": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.08").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Hazardous substance barrier": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.09").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "High purity sorting possible": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.10").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Use of easily recyclable materials": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.11").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Recycling collection rate": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R8.12").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "R9: Recover": {
                "Recover (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Waste diversion from landfill": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Potential recovery": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Hazardous waste directed to disposal": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Non-hazardous waste directed to disposal": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Energy recoverability benefit": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Raw materials input": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="R9.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
            "RE: Circularity enablers": {
                "Circularity enablers (total)": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Process data access conditions": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.01").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Hardware and software access conditions": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.02").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Standardised component ratio": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.03").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Component coding used": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.04").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Material coding used": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.05").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
                "Tracking device used": safe(CircularityScore.objects.filter(evaluation__product=product_model, indicator__id="RE.06").order_by("-evaluation__assessment_date").values_list("value", flat=True).first()),
            },
        }

    return D

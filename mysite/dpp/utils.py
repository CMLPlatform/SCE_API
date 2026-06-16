
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

    return {
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
    }

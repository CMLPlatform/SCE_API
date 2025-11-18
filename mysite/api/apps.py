import sys
from django.apps import AppConfig
#NOTE: This file can be deleted if the commented code is not used.


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    # def ready(self):
    #     if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
    #         return  # Stop here during migrations

    #     from .models import INSTRUCTION_TYPES
    #     from .models import Instruction

    #     for key in INSTRUCTION_TYPES:
    #         Instruction.objects.get_or_create(label=key, defaults={'label': key})

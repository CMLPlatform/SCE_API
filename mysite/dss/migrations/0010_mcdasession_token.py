import uuid

from django.db import migrations, models


def fill_tokens(apps, schema_editor):
    McdaSession = apps.get_model("dss", "McdaSession")
    for session in McdaSession.objects.filter(token__isnull=True):
        session.token = uuid.uuid4()
        session.save(update_fields=["token"])


class Migration(migrations.Migration):

    dependencies = [
        ("dss", "0009_delete_localorder_group_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="mcdasession",
            name="token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(fill_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="mcdasession",
            name="token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

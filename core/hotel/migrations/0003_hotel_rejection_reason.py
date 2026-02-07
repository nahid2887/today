# Generated migration for rejection_reason field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0002_hotel_commission_rate'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotel',
            name='rejection_reason',
            field=models.TextField(blank=True, help_text='Reason for hotel rejection', null=True),
        ),
    ]

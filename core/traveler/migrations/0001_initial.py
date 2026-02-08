# Generated migration for FavoriteHotel and HotelRating models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hotel', '0005_specialoffer'),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteHotel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('hotel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by', to='hotel.hotel')),
                ('traveler', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorite_hotels', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-added_at'],
                'unique_together': {('traveler', 'hotel')},
            },
        ),
        migrations.CreateModel(
            name='HotelRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(decimal_places=1, help_text='Rating from 1 to 5', max_digits=2, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('review', models.TextField(blank=True, help_text='Optional review text', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hotel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='hotel.hotel')),
                ('traveler', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hotel_ratings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('traveler', 'hotel')},
            },
        ),
    ]

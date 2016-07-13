# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0019_org_surveyor_password'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('channels', '0032_channelevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='AirtimeEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this item is active, use this instead of deleting')),
                ('created_on', models.DateTimeField(help_text='When this item was originally created', auto_now_add=True)),
                ('modified_on', models.DateTimeField(help_text='When this item was last modified', auto_now=True)),
                ('status', models.CharField(default=b'P', help_text=b'The state this event is currently in', max_length=1, choices=[(b'P', b'Pending'), (b'C', b'Complete'), (b'F', b'Failed')])),
                ('recipient', models.CharField(max_length=64)),
                ('amount', models.FloatField()),
                ('denomination', models.CharField(max_length=32, null=True, blank=True)),
                ('transaction_id', models.CharField(max_length=256, null=True, blank=True)),
                ('reference_operator', models.CharField(max_length=64, null=True, blank=True)),
                ('airtime_amount', models.CharField(max_length=32, null=True, blank=True)),
                ('last_message', models.CharField(max_length=256, null=True, blank=True)),
                ('data', models.TextField(null=True, blank=True)),
                ('event_log', models.TextField(null=True, blank=True)),
                ('channel', models.ForeignKey(blank=True, to='channels.Channel', help_text=b'The channel that this event is relating to', null=True)),
                ('created_by', models.ForeignKey(related_name='events_airtimeevent_creations', to=settings.AUTH_USER_MODEL, help_text='The user which originally created this item')),
                ('modified_by', models.ForeignKey(related_name='events_airtimeevent_modifications', to=settings.AUTH_USER_MODEL, help_text='The user which last modified this item')),
                ('org', models.ForeignKey(help_text=b'The organization that this event was triggered for', to='orgs.Org')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]

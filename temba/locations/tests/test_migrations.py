from django.contrib.gis.geos.collections import MultiPolygon
from django.core.management import call_command

from temba.locations.models import AdminBoundary, BoundaryAlias, Location, LocationAlias
from temba.tests import MigrationTest, matchers


class PopulateLocationsTest(MigrationTest):
    app = "locations"
    migrate_from = "0033_location_locationalias_location_locations_by_name_and_more"
    migrate_to = "0034_populate_locations"

    def setUpBeforeMigration(self, apps):
        self.assertEqual(0, AdminBoundary.objects.all().count())
        call_command("import_geojson", "test-data/rwanda.zip")
        self.assertEqual(9, AdminBoundary.objects.all().count())

        self.country = AdminBoundary.objects.get(level=0)
        self.assertIsInstance(self.country.simplified_geometry, MultiPolygon)
        self.assertEqual(self.country.simplified_geometry.geojson, matchers.String())

        self.state1 = AdminBoundary.objects.get(name="Kigali City", level=1)
        self.district1 = AdminBoundary.objects.get(name="Gasabo District", level=2)

        BoundaryAlias.create(self.org, self.admin, self.state1, "Kigari")
        BoundaryAlias.create(self.org2, self.admin2, self.state1, "Chigali")

        self.country.update_path()

        self.org.country = self.country
        self.org.save(update_fields=("country",))

        self.assertEqual(9, AdminBoundary.objects.all().count())
        self.assertEqual(2, BoundaryAlias.objects.all().count())

        self.assertIsNone(self.org.location)
        self.assertEqual(0, Location.objects.all().count())
        self.assertEqual(0, LocationAlias.objects.all().count())

    def test_migrations(self):
        self.org.refresh_from_db()
        self.assertIsNotNone(self.org.location)
        country_location = Location.objects.filter(level=0).get()
        self.assertEqual(country_location, self.org.location)
        self.assertEqual(country_location.geometry, matchers.Dict())

        self.org2.refresh_from_db()
        self.assertIsNone(self.org2.country)
        self.assertIsNone(self.org2.location)

        self.assertEqual(9, AdminBoundary.objects.all().count())
        self.assertEqual(2, BoundaryAlias.objects.all().count())

        self.assertEqual(9, Location.objects.all().count())
        self.assertEqual(2, LocationAlias.objects.all().count())

        self.assertEqual(1, Location.objects.filter(level=0).count())
        self.assertEqual(5, Location.objects.filter(level=1).count())
        self.assertEqual(3, Location.objects.filter(level=2).count())
        self.assertEqual(0, Location.objects.filter(level=3).count())

        self.assertEqual(1, LocationAlias.objects.filter(org=self.org).count())
        self.assertEqual("Kigari", LocationAlias.objects.filter(org=self.org).get().name)

        self.assertEqual(1, LocationAlias.objects.filter(org=self.org2).count())
        self.assertEqual("Chigali", LocationAlias.objects.filter(org=self.org2).get().name)
        self.org2.refresh_from_db()
        self.assertIsNone(self.org2.country)
        self.assertIsNone(self.org2.location)

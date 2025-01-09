import os.path
from zipfile import ZipFile

import geojson
import regex

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from temba.locations.models import Location


class Command(BaseCommand):
    help = "Import our geojson zip file format, updating all our OSM data accordingly."

    def add_arguments(self, parser):
        parser.add_argument("files", nargs="+")
        parser.add_argument(
            "--country", dest="country", default=None, help="Only process the location files for this country osm id"
        )

    def import_file(self, filename, file):
        admin_json = geojson.loads(file.read())

        # we keep track of all the osm ids we've seen because we remove all admin levels at this level
        # which weren't seen. (they have been removed)
        seen_osm_ids = set()
        osm_id = None

        # parse our filename.. they are in the format:
        # 192787admin2_simplified.json
        match = regex.match(r"(\w+\d+)admin(\d)(_simplified)?\.json$", filename, regex.V0)
        level = None
        is_simplified = None
        if match:
            level = int(match.group(2))
            is_simplified = True if match.group(3) else False
        else:
            # else parse other filenames that are in
            # admin_level_0_simplified.json format.
            match = regex.match(r"admin_level_(\d)(_simplified)?\.json$", filename, regex.V0)
            if match:
                level = int(match.group(1))
                is_simplified = True if match.group(2) else False
            else:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}', doesn't match file pattern."))
                return None, set()

        # for each of our features
        for feature in admin_json["features"]:
            # what level are we?
            props = feature.properties

            # get parent id which is set in new file format
            parent_osm_id = str(props.get("parent_id"))

            # if parent_osm_id is not set and not LEVEL_COUNTRY check for old file format
            if parent_osm_id == "None" and level != Location.LEVEL_COUNTRY:
                if level == Location.LEVEL_STATE:
                    parent_osm_id = str(props["is_in_country"])
                elif level == Location.LEVEL_DISTRICT:
                    parent_osm_id = str(props["is_in_state"])
                elif level == Location.LEVEL_WARD:
                    parent_osm_id = str(props["is_in_state"])

            osm_id = str(props["osm_id"])
            name = props.get("name", "")
            if not name or name == "None" or level == Location.LEVEL_COUNTRY:
                name = props.get("name_en", "")

            # try to find parent, bail if we can't
            parent = None
            if parent_osm_id != "None":
                parent = Location.objects.filter(osm_id=parent_osm_id).first()
                if not parent:
                    self.stdout.write(
                        self.style.SUCCESS(f"Skipping {name} ({osm_id}) as parent {parent_osm_id} not found.")
                    )
                    continue

            # try to find existing admin level by osm_id
            location = Location.objects.filter(osm_id=osm_id)

            # didn't find it? what about by name?
            if not location:
                location = Location.objects.filter(parent=parent, name__iexact=name)

            # skip over items with no geometry
            if not feature["geometry"] or not feature["geometry"]["coordinates"]:
                continue  # pragma: can't cover

            polygons = []
            if feature["geometry"]["type"] == "Polygon":
                polygons.append(geojson.Polygon(coordinates=feature["geometry"]["coordinates"]))
            elif feature["geometry"]["type"] == "MultiPolygon":
                for polygon in feature["geometry"]["coordinates"]:
                    polygons.append(geojson.Polygon(coordinates=polygon))
            else:
                raise Exception("Error importing %s, unknown geometry type '%s'" % (name, feature["geometry"]["type"]))

            geometry = geojson.loads(geojson.dumps(geojson.MultiPolygon(polygons)))

            kwargs = dict(osm_id=osm_id, name=name, level=level, parent=parent)
            if is_simplified:
                kwargs["simplified_geometry"] = geometry

            # if this is an update, just update with those fields
            if location:
                if not parent:
                    kwargs["path"] = name
                else:
                    kwargs["path"] = parent.path + Location.PADDED_PATH_SEPARATOR + name

                self.stdout.write(self.style.SUCCESS(f" ** updating {name} ({osm_id})"))
                location = location.first()
                location.update(**kwargs)

                # update any children
                location.update_path()

            # otherwise, this is new, so create it
            else:
                self.stdout.write(self.style.SUCCESS(f" ** adding {name} ({osm_id})"))
                Location.create(**kwargs)

            # keep track of this osm_id
            seen_osm_ids.add(osm_id)

        # now remove any unseen locations
        if osm_id:
            last_location = Location.objects.filter(osm_id=osm_id).first()
            if last_location:
                self.stdout.write(self.style.SUCCESS(f" ** removing unseen locations ({osm_id})"))
                country = last_location.get_root()
                unseen_locations = country.get_descendants().filter(level=level).exclude(osm_id__in=seen_osm_ids)
                deleted_count = 0
                for unseen_location in unseen_locations:
                    unseen_location.release()
                    deleted_count += 1
                if deleted_count > 0:
                    self.stdout.write(f" ** Unseen locations removed: {deleted_count}")

                return country, seen_osm_ids
            else:
                return None, set()
        else:
            return None, set()

    def handle(self, *args, **options):
        files = options["files"]

        zipfile = None
        if files[0].endswith(".zip"):
            zipfile = ZipFile(files[0], "r")
            filepaths = zipfile.namelist()

        else:
            filepaths = list(files)

        # are we filtering by a prefix?
        prefix = ""
        if options["country"]:
            prefix = "%sadmin" % options["country"]

        # sort our filepaths, this will make sure we import 0 levels before 1 and before 2
        filepaths.sort()

        country = None
        updated_osm_ids = set()

        with transaction.atomic():
            # for each file they have given us
            for filepath in filepaths:
                filename = os.path.basename(filepath)
                # if it ends in json, then it is geojson, try to parse it
                if filename.startswith(prefix) and filename.endswith("json"):
                    # read the file entirely
                    self.stdout.write(self.style.SUCCESS(f"=== parsing {filename}"))

                    # if we are reading from a zipfile, read it from there
                    if zipfile:
                        with zipfile.open(filepath) as json_file:
                            country, seen_osm_ids = self.import_file(filename, json_file)

                    # otherwise, straight off the filesystem
                    else:
                        with open(filepath) as json_file:
                            country, seen_osm_ids = self.import_file(filename, json_file)

                    # add seen osm_ids to the all_upated_osm_ids collection
                    updated_osm_ids = updated_osm_ids.union(seen_osm_ids)

            if country is None:
                return

            # remove all other unseen locations from the database for the country
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                DELETE FROM locations_location WHERE id IN (

                with recursive location_set(id, parent_id, name, depth, path, cycle, osm_id) AS (
  SELECT ab.id, ab.parent_id, ab.name, 1, ARRAY[ab.id], false, ab.osm_id
  from locations_location ab
  WHERE id = %s

  UNION ALL

  SELECT ab.id, ab.parent_id, ab.name, abs.depth+1, abs.path || ab.id, ab.id = ANY(abs.path), ab.osm_id
  from locations_location ab , location_set abs
  WHERE not cycle AND ab.parent_id = abs.id
)
SELECT
  abs.id
from location_set abs
WHERE NOT (abs.osm_id = ANY(%s)))
                """,
                    (country.id, list(updated_osm_ids)),
                )
                self.stdout.write(self.style.SUCCESS(f"Other unseen locations removed: {cursor.rowcount}"))

        if country:
            self.stdout.write(self.style.SUCCESS((f" ** updating paths for all of {country.name}")))
            country.update_path()

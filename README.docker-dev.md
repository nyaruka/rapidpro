# Using docker-compose for development

You can create an isolated development environment using *docker* and *docker-compose*.
This isolated development environment includes a postgres database service and a redis service.

The environment is based on `ubuntu:16.04` image which is the operating system we recommend to use in production.

## Build the rapidpro image

* `docker-compose build rapidpro`

## Run RapidPro service

* `docker-compose up -d`
* monitor logs in a terminal:
   * `docker-compose logs -f` 

## Create database user and database

* `docker-compose exec db createuser -s -U postgres temba`
* `docker-compose exec db createdb -U temba temba`
* `docker-compose exec db psql -U temba -d temba -c 'CREATE EXTENSION postgis;CREATE EXTENSION postgis_topology;CREATE EXTENSION hstore;'`

## Prepare the environment

* symlink the settings file: `ln -s temba/settings.py.docker_dev temba/settings.py`
* `docker-compose run rapidpro python manage.py migrate`
* `docker-compose run rapidpro bower --allow-root install`

## Execute tests and code quality checks

* `docker-compose run rapidpro coverage run manage.py test --noinput --verbosity=2`
* `docker-compose run rapidpro npm run test`
* `docker-compose run rapidpro flake8`

## Generate some test data

* `docker-compose run rapidpro python manage.py test_db generate --orgs=10 --contacts=10000`
    * use `admin1:Querty123` to login as an admin user for org #1
* `docker-compose run rapidpro python manage.py test_db simulate --runs 1`

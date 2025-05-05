# RapidPro

[![tag](https://img.shields.io/github/tag/nyaruka/rapidpro.svg)](https://github.com/nyaruka/rapidpro/releases)
[![Build Status](https://github.com/nyaruka/rapidpro/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nyaruka/rapidpro/actions?query=workflow%3ACI)
[![codecov](https://codecov.io/gh/nyaruka/rapidpro/branch/main/graph/badge.svg)](https://codecov.io/gh/nyaruka/rapidpro)

RapidPro is a cloud based SaaS developed by [TextIt](https://textit.com) for visually building interactive messaging 
applications. To see what it can do, signup for a free trial account at [textit.com](https://textit.com).

## Technology Stack

- [PostgreSQL](https://www.postgresql.org)
- [Redis](https://redis.io)
- [Elasticsearch](https://www.elastic.co/elasticsearch)
- [S3](https://aws.amazon.com/s3/)
- [DynamoDB](https://aws.amazon.com/dynamodb/)
- [Cloudwatch](https://aws.amazon.com/cloudwatch/)

## Versioning

Major releases are made every 6 months on a set schedule. We target January as a major release (e.g. `10.0.0`), then
July as the stable dot release (e.g. `10.2.0`). Unstable releases (i.e. _development_ versions) have odd minor versions
(e.g. `10.1.*`, `10.3.*`).

To upgrade from one stable release to the next, you must first install and run the migrations for the latest stable 
release you are on, then every stable release afterwards. For example if you're upgrading from `7.4` to `8.0`, you 
need to upgrade to `7.4.2` before upgrading to `8.0`.

### Stable Versions

The set of versions that make up the latest stable release are:

- [RapidPro 10.0.1](https://github.com/nyaruka/rapidpro/releases/tag/v10.0.1)
- [Mailroom 10.0.0](https://github.com/nyaruka/mailroom/releases/tag/v10.0.0)
- [Courier 10.0.0](https://github.com/nyaruka/courier/releases/tag/v10.0.0)
- [Indexer 10.0.0](https://github.com/nyaruka/rp-indexer/releases/tag/v10.0.0)
- [Archiver 10.0.0](https://github.com/nyaruka/rp-archiver/releases/tag/v10.0.0)

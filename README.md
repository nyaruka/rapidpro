# Temba

[![Build Status](https://github.com/nyaruka/temba/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nyaruka/temba/actions?query=workflow%3ACI)

Temba is the frontend component of the RapidPro platform developed by [TextIt](https://textit.com). It's a cloud based SaaS for 
visually building interactive messaging applications. To see what it can do, signup for a free trial account at [textit.com](https://textit.com).

## Stack

- [PostgreSQL](https://www.postgresql.org)
- [Valkey](https://valkey.io)
- [Elasticsearch](https://www.elastic.co/elasticsearch)
- [Squid](https://www.squid-cache.org)
- [Centrifugo](https://centrifugal.dev)
- [S3](https://aws.amazon.com/s3/)
- [DynamoDB](https://aws.amazon.com/dynamodb/)
- [Hugging Face](https://github.com/huggingface/text-embeddings-inference)
- [Cloudwatch](https://aws.amazon.com/cloudwatch/)

## Snapshots

Every 6 months we [publish snapshots](https://github.com/nyaruka/temba/discussions), which are a set of stable versions of the components that make up the platform. 
To upgrade from one snapshot to the next, you must first install and run the migrations for the latest snapshot you are on, then every snapshot afterwards.

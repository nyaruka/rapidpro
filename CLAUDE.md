# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Code Quality and Checks

- **Primary check script**: `./code_check.py` - Run before committing, checks formatting and missing database migrations
- **Code formatting**:
  - `black temba` - Format Python code
  - `isort temba` - Sort imports
  - `ruff check temba` - Lint Python code
- **Database migrations**: `python manage.py makemigrations --check` - Check for missing migrations

### Testing

- **Run tests**: `python manage.py test` with `--keepdb` flag to speed up subsequent runs
- **Test a specific app**: `python manage.py test temba.contacts --keepdb`

### Frontend Build

- **Tailwind CSS build**: `yarn run tw-build`
- **Watch Tailwind changes**: `yarn run tw-watch`

### Django Management

- **Development server**: `python manage.py runserver`
- **Create migrations**: `python manage.py makemigrations`
- **Apply migrations**: `python manage.py migrate`
- **Django shell**: `python manage.py shell`

## Architecture Overview

RapidPro is a Django-based web application for building interactive messaging flows. The ecosystem consists of:

- **RapidPro**: Main Django web application (this repository)
- **Mailroom**: Flow
- **Courier**: Message channel gateway
- **rp-indexer**: Elasticsearch indexing service
- **rp-archiver**: Data archiving service

### Core Technology Stack

- **Backend**: Django 5.2, Python 3.12, PostgreSQL
- **Frontend**: React 16.13, Less/Tailwind CSS, temba-components
- **Cache/Queue**: Valkey (Redis-compatible)
- **Search**: Elasticsearch
- **Storage**: S3/Cloud storage
- **Message Queue**: Celery with Redis

### Database Architecture

- Primary database: PostgreSQL with PostGIS extensions
- Logs and archives: DynamoDB
- Search indices: Elasticsearch
- Default dev database: `temba` user/password on `temba` database

## Project Structure

- `temba/` - Main Django application directory
  - `contacts/` - Contact and contact group management
  - `flows/` - Flow definitions, runs, and sessions
  - `msgs/` - Message handling and broadcasts
  - `channels/` - Communication channel integrations
  - `campaigns/` - Campaign and event management
  - `orgs/` - Organization and user management
  - `api/` - REST API endpoints (v2)
  - `mailroom/` - Mailroom client integration
- `templates/` - Django HTML templates
- `static/` - Static assets (CSS, JS, images)
- `media/` - Test files and media assets

### Key Models and Concepts

- **Flows**: Visual workflow definitions with nodes and actions
- **Contacts**: End users with URNs (phone numbers, emails, etc.)
- **Messages**: Inbound/outbound communications
- **Channels**: SMS, WhatsApp, and other messaging integrations
- **Organizations**: Multi-tenant workspace isolation

## Development Guidelines

### Python Code Style

- Use Black formatter with 120 character line length
- Use isort for import organization
- Follow Django conventions and patterns
- Don't put placeholder text in `__init__.py` files
- Avoid lazy imports unless necessary for cyclic dependencies

### Testing

- Use Django's TestCase classes
- Always include `--keepdb` flag when running tests
- Test files located in `tests/` subdirectories within each app

### Frontend Development

- React components use legacy class-based syntax (React 16.13)
- Tailwind CSS for styling with custom configuration
- temba-components library provides reusable UI components

## Configuration

### Development Setup

- Copy `temba/settings.py.dev` for local development
- Requires PostgreSQL with PostGIS, Valkey/Redis instance
- Mailroom service runs on `http://localhost:8090` by default
- Environment variables can override database and service URLs

### Key Settings Files

- `temba/settings_common.py` - Shared settings
- `temba/settings.py.dev` - Development configuration example
- `temba/settings_security.py` - Security-related settings

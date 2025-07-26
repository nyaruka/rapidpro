# WhatsApp Template Manual Sync Tool

This tool allows you to manually fetch WhatsApp templates from Meta's WhatsApp Business API and insert them into your RapidPro database, bypassing the automatic cron job system.

## Prerequisites

1. **WhatsApp Business Account**: You need a verified WhatsApp Business Account with Meta
2. **System User Access Token**: A valid access token for your WhatsApp Business Account
3. **WABA ID**: Your WhatsApp Business Account ID
4. **RapidPro Database Access**: The script needs to run in your RapidPro environment

## Installation

The management command is located at:
```
temba/templates/management/commands/fetch_whatsapp_templates.py
```

No additional installation is required - it uses existing RapidPro dependencies.

## Usage

### Basic Syntax
```bash
python manage.py fetch_whatsapp_templates --waba-id <WABA_ID> --access-token <ACCESS_TOKEN> [OPTIONS]
```

### Required Parameters

- `--waba-id`: Your WhatsApp Business Account ID
- `--access-token`: System User Access Token for WhatsApp Business API

### Channel Options (choose one)

**Option 1: Use Existing Channel**
```bash
--channel-id <CHANNEL_ID>
```

**Option 2: Create New Channel**
```bash
--create-channel --org-id <ORG_ID> --wa-number <PHONE_NUMBER> --wa-verified-name <BUSINESS_NAME>
```

### Examples

#### 1. Use Existing Channel
```bash
python manage.py fetch_whatsapp_templates \
    --waba-id 123456789012345 \
    --access-token EAABwzLixnjYBOZCxxx \
    --channel-id 5
```

#### 2. Create New Channel and Fetch Templates
```bash
python manage.py fetch_whatsapp_templates \
    --waba-id 123456789012345 \
    --access-token EAABwzLixnjYBOZCxxx \
    --org-id 1 \
    --wa-number "+1234567890" \
    --wa-verified-name "Your Business Name" \
    --create-channel
```

#### 3. Dry Run (Preview Only)
```bash
python manage.py fetch_whatsapp_templates \
    --waba-id 123456789012345 \
    --access-token EAABwzLixnjYBOZCxxx \
    --channel-id 5 \
    --dry-run \
    --verbose
```

#### 4. Create Channel with Additional Parameters
```bash
python manage.py fetch_whatsapp_templates \
    --waba-id 123456789012345 \
    --access-token EAABwzLixnjYBOZCxxx \
    --org-id 1 \
    --wa-number "+1234567890" \
    --wa-verified-name "Your Business Name" \
    --wa-currency "USD" \
    --wa-business-id "987654321" \
    --wa-namespace "your_namespace" \
    --create-channel \
    --verbose
```

## Command Options

### Required
- `--waba-id`: WhatsApp Business Account ID
- `--access-token`: System User Access Token

### Channel Selection (one required)
- `--channel-id`: Use existing channel ID
- `--create-channel`: Create new channel (requires additional params)

### New Channel Parameters (required with --create-channel)
- `--org-id`: Organization ID in RapidPro
- `--wa-number`: WhatsApp phone number (e.g., "+1234567890")
- `--wa-verified-name`: Verified business name

### Optional New Channel Parameters
- `--wa-currency`: Account currency (default: "USD")
- `--wa-business-id`: Facebook Business ID
- `--wa-namespace`: Message template namespace

### Execution Options
- `--dry-run`: Fetch templates but don't insert into database
- `--verbose`: Show detailed output including template details
- `--verbosity {0,1,2,3}`: Set Django verbosity level

## How It Works

1. **API Fetching**: Makes authenticated requests to `https://graph.facebook.com/v18.0/{waba_id}/message_templates`
2. **Pagination**: Automatically handles paginated responses from Meta's API
3. **Channel Management**: Either uses existing channel or creates new WhatsApp channel
4. **Template Processing**: Uses RapidPro's existing `TemplateTranslation.update_local()` logic
5. **Database Insertion**: Safely inserts/updates templates using the same code paths as the built-in sync

## Output

### Successful Run
```
Fetching templates from Meta WhatsApp Business API...
Found 15 templates
Successfully processed 15 templates for channel 5 (My WhatsApp Channel)
```

### Dry Run Output
```
Fetching templates from Meta WhatsApp Business API...
Found 15 templates

Template Details:
--------------------------------------------------
Name: welcome_message
  Status: APPROVED
  Language: en
  ID: 1234567890
  Components: 1

Name: order_confirmation
  Status: PENDING
  Language: en
  ID: 1234567891
  Components: 2

Dry run mode - no templates were inserted
```

## Getting Your Credentials

### WhatsApp Business Account ID (WABA ID)
1. Go to Facebook Business Manager
2. Navigate to WhatsApp Business Accounts
3. Your WABA ID is shown in the account details

### System User Access Token
1. Create a System User in Facebook Business Manager
2. Assign WhatsApp Business Management permissions
3. Generate a permanent access token
4. The token should have these permissions:
   - `whatsapp_business_management`
   - `whatsapp_business_messaging`

### Finding Organization ID
```bash
python manage.py shell
>>> from temba.orgs.models import Org
>>> Org.objects.all().values('id', 'name')
```

### Finding Existing Channel ID
```bash
python manage.py shell
>>> from temba.channels.models import Channel
>>> Channel.objects.filter(channel_type='WAC', is_active=True).values('id', 'name', 'address')
```

## Troubleshooting

### Common Errors

**"Channel X is not a WhatsApp channel"**
- The specified channel ID is not a WhatsApp (WAC) channel type

**"Failed to fetch templates from Meta API: 401"**
- Invalid or expired access token
- Check token permissions and expiration

**"No admin users found for organization X"**
- The organization has no admin users
- Add an admin user to the organization first

**"No templates found in your WhatsApp Business Account"**
- No templates exist in your WABA
- Create templates in WhatsApp Business Manager first

### API Rate Limits
Meta's API has rate limits. If you hit them:
- Wait a few minutes and retry
- The script automatically handles pagination to minimize requests

### Database Permissions
Ensure the Django user has permissions to:
- Read from `orgs_org`, `channels_channel`, `users_user` tables
- Write to `templates_template`, `templates_templatetranslation` tables

## Security Notes

- Access tokens are sensitive - don't log them or include in version control
- Use environment variables for credentials in production
- The script validates all inputs and uses existing RapidPro security measures
- Dry run mode is recommended for first-time usage

## Support

For issues with:
- **RapidPro Integration**: Check Django logs and database permissions
- **Meta API**: Verify credentials and WABA status in Facebook Business Manager
- **Template Processing**: Compare with existing RapidPro template sync logs
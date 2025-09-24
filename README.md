# Email CSV Extractor

Auto CSV log file ingestion from email to Microsoft Teams using Python. This system polls a mailbox via MS Graph API, filters messages by sender/subject patterns, downloads CSV attachments, and uploads them to a SharePoint folder in a target Teams channel. Designed for PowerBI connectivity with no manual steps or paid licenses required.

## Features

- **OAuth App-Only Authentication**: Secure authentication using Azure AD app-only flow
- **MS Graph API Integration**: Polls mailboxes and accesses SharePoint via Microsoft Graph
- **Intelligent Filtering**: Filter emails by sender patterns, subject patterns, and message age
- **CSV Processing**: Automatic detection and validation of CSV attachments
- **Large File Support**: Chunked upload for files larger than 4MB
- **Modular Architecture**: SOLID design principles with dependency injection
- **100% Test Coverage**: Comprehensive test suite with pytest
- **Structured Logging**: JSON-structured logging for observability
- **CLI Interface**: Easy-to-use command-line interface
- **Extensible Design**: Easy to add new features like advanced parsing or webhook triggers

## Architecture

The system follows SOLID design principles with a modular architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  Authentication  │    │  Configuration  │
│                 │    │    Provider      │    │    Manager      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                ┌────────────────────────────┐
                │   Dependency Container     │
                │  (Dependency Injection)    │
                └────────────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │   Email CSV Processor   │
                    │   (Main Orchestrator)   │
                    └─────────────────────────┘
                                 │
      ┌──────────────┬───────────┼────────────┬─────────────────┐
      │              │           │            │                 │
┌──────────┐  ┌─────────────┐  ┌────────┐  ┌──────────┐  ┌─────────────┐
│  Email   │  │   Message   │  │  CSV   │  │SharePoint│  │   Logger    │
│ Poller   │  │   Filter    │  │Download│  │ Uploader │  │             │
└──────────┘  └─────────────┘  └────────┘  └──────────┘  └─────────────┘
```

## Prerequisites

- Python 3.8+
- Azure AD Application with appropriate permissions
- Microsoft Teams setup with target channel
- Access to the mailbox to monitor

## Azure AD App Registration

1. Register a new application in Azure AD
2. Grant the following Microsoft Graph API permissions:
   - `Mail.Read` (Application permission)
   - `Files.ReadWrite` (Application permission)
   - `Sites.ReadWrite.All` (Application permission)
3. Generate a client secret
4. Note down the Client ID, Client Secret, and Tenant ID

## Installation

```bash
# Clone the repository
git clone https://github.com/aaweaver-actuary/email-csv-extractor.git
cd email-csv-extractor

# Install the package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your actual values:
```bash
# Azure AD Authentication
AZURE_CLIENT_ID=your-azure-app-client-id
AZURE_CLIENT_SECRET=your-azure-app-client-secret
AZURE_TENANT_ID=your-azure-tenant-id

# Email Configuration
EMAIL_MAILBOX_ADDRESS=your-monitored-mailbox@company.com

# SharePoint/Teams Configuration
SHAREPOINT_TEAM_ID=your-teams-team-id
SHAREPOINT_CHANNEL_ID=your-teams-channel-id

# Message Filtering
FILTER_SENDER_PATTERNS=reports@company.com,automation@partner.com
FILTER_SUBJECT_PATTERNS=daily report,csv export
```

## Usage

### Command Line Interface

```bash
# Test authentication
email-csv-extractor test-auth

# Test email polling
email-csv-extractor test-email

# Validate configuration
email-csv-extractor validate-config

# Run once (single processing cycle)
email-csv-extractor run --once

# Run in dry-run mode (don't upload files)
email-csv-extractor run --dry-run

# Continuous polling (production mode)
email-csv-extractor run
```

### Programmatic Usage

```python
from email_csv_extractor import DependencyContainer
from email_csv_extractor.config.settings import EnvironmentConfigurationManager
from email_csv_extractor.workflow.processor import EmailCsvProcessor

# Setup
config_manager = EnvironmentConfigurationManager()
container = setup_dependency_container(config_manager)
processor = EmailCsvProcessor(container, logger)

# Process emails once
stats = await processor.process_emails_once()
print(f"Processed {stats['files_uploaded']} files")
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=email_csv_extractor --cov-report=html

# Run specific test file  
pytest tests/unit/core/test_container.py -v

# Run with specific coverage target
pytest --cov=email_csv_extractor --cov-fail-under=100
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Configuration Options

### Authentication
- `AZURE_CLIENT_ID`: Azure AD Application Client ID
- `AZURE_CLIENT_SECRET`: Azure AD Application Client Secret  
- `AZURE_TENANT_ID`: Azure AD Tenant ID
- `AZURE_AUTHORITY`: Azure AD Authority URL (default: https://login.microsoftonline.com)

### Email Polling
- `EMAIL_MAILBOX_ADDRESS`: Email address to monitor
- `EMAIL_POLLING_INTERVAL`: Polling interval in seconds (default: 300)
- `EMAIL_MAX_MESSAGES_PER_POLL`: Maximum messages per poll (default: 50)

### SharePoint Upload
- `SHAREPOINT_TEAM_ID`: Microsoft Teams Team ID
- `SHAREPOINT_CHANNEL_ID`: Microsoft Teams Channel ID
- `SHAREPOINT_TARGET_FOLDER`: Target folder path (default: "Shared Documents/CSV Files")

### Message Filtering
- `FILTER_SENDER_PATTERNS`: Comma-separated sender patterns
- `FILTER_SUBJECT_PATTERNS`: Comma-separated subject patterns
- `FILTER_MAX_AGE_DAYS`: Maximum message age in days (default: 7)

### Application Settings
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `TEMP_DIRECTORY`: Temporary directory for file processing

## PowerBI Integration

Once files are uploaded to SharePoint, you can connect PowerBI to the SharePoint folder:

1. In PowerBI, select "Get Data" → "SharePoint folder"
2. Enter your SharePoint site URL
3. Navigate to the configured target folder
4. PowerBI will automatically refresh when new CSV files are added

## Monitoring and Logging

The application provides structured JSON logging for easy monitoring:

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "info",
  "logger": "email-csv-extractor",
  "message": "Successfully uploaded CSV to SharePoint",
  "attachment_name": "daily_report.csv",
  "upload_url": "https://sharepoint.com/...",
  "sender": "reports@company.com"
}
```

## Error Handling

The system includes comprehensive error handling with automatic retries:

- **Authentication failures**: Automatic token refresh
- **Network timeouts**: Exponential backoff retry
- **Large file uploads**: Chunked upload with resume capability
- **Invalid CSV files**: Content validation and skip

## Security Considerations

- Uses OAuth app-only authentication (no user credentials stored)
- Client secrets should be stored securely (Azure Key Vault recommended)
- All network communication uses HTTPS
- Temporary files are automatically cleaned up
- No sensitive data is logged

## Extensibility

The modular design makes it easy to extend:

### Adding New File Types
Implement a new `AttachmentDownloader` and register it in the container.

### Adding Webhook Triggers
Create a new `EmailPoller` implementation that listens to webhooks instead of polling.

### Advanced Parsing
Extend the `MessageFilter` to support more complex filtering logic.

### Custom Upload Destinations
Implement a new `SharePointUploader` for different destinations.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Ensure 100% test coverage
5. Run code quality checks
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
1. Check the [documentation](#usage)
2. Review [existing issues](https://github.com/aaweaver-actuary/email-csv-extractor/issues)
3. Create a new issue with detailed information
# Terminal Connect Test Application

A Flask application for testing Terminal Connect API integration with support for sales, refunds, reversals, postback inspection, and user management with invite system.

## Features

- **Automatic Database Setup**
  - Zero-configuration database initialization
  - Automatic migration handling
  - Admin user creation from environment variables
  - Health monitoring and error recovery
- **User Management**
  - Admin and regular user roles
  - Invite-based registration system
  - User removal and re-invitation support
  - Profile management and password changes
- **Configuration Management**
  - Environment selection (Dev Test/Sandbox/Production)
  - MID, TID, and API key configuration
  - Custom postback URL support
  - Built-in postback handling at `/postback` endpoint
- **Transaction Operations**
  - Process sales
  - Process unlinked refunds
  - Process linked refunds (requires parent intent ID)
  - Process reversals
- **Postback Inspection**
  - All postbacks sent to `/postback` are recorded in a file
  - Postbacks are viewable at `/postbacks` in a table with expandable details
  - Postbacks are cleared daily
  - Sensitive headers (e.g., Authorization) are masked in the UI
- **Health Monitoring**
  - Built-in health check endpoint at `/health`
  - Database connection monitoring
  - Docker health check integration

## 🚀 Quick Start

### Option 1: Local Development (Recommended)

**One command setup:**
```bash
# Clone the repository
git clone <repository-url>
cd terminal-connect-test

# Copy environment configuration
cp .env.example .env

# Edit .env with your credentials (see Environment Variables section)
# Then run:
python run.py
```

This will automatically:
- Set up the database and run migrations
- Create admin user (if credentials provided)
- Start the development server at `http://localhost:5000`

### Option 2: Docker Local Development

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env with your credentials, then:
docker compose -f docker-compose.local.yml up --build
```

### Option 3: Docker Production

```bash
# Create .env file with production credentials
cp .env.example .env

# Edit .env with production values, then:
docker compose up -d
```

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Flask Configuration
FLASK_APP=app:create_app
FLASK_ENV=development  # or production
SECRET_KEY=your-secret-key-here

# Database (automatic for Docker, configure for local)
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# Admin User (automatically created during setup)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-secure-admin-password

# Email Service (for sending invites)
BREVO_API_KEY=your-brevo-api-key-here

# Payment Gateway Configuration
MID=your-merchant-id
TID=your-terminal-id
API_KEY=your-api-key

# Optional
DEBUG=false  # Set to true for verbose Docker logging
```

## Setup Options

### Manual Local Setup

If you prefer manual setup:

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database (optional - done automatically):**
   ```bash
   python init_db.py
   ```

5. **Run application:**
   ```bash
   python run.py
   # OR manually:
   flask run --host=0.0.0.0 --port=5000
   ```

### Docker Setup

#### Local Development
```bash
# Build and run with development settings
docker compose -f docker-compose.local.yml up --build

# With custom environment variables
ADMIN_EMAIL=dev@localhost ADMIN_PASSWORD=devpass docker compose -f docker-compose.local.yml up --build
```

#### Production Deployment
```bash
# Uses prebuilt image from GitHub Container Registry
docker compose up -d

# Check logs
docker compose logs -f web

# Check health
curl http://localhost:5001/health
```

## Database Management

### Automatic Initialization ✅
- **No manual commands needed** - Database automatically initializes
- **Migration handling** - Creates and applies migrations automatically
- **Admin user creation** - Uses environment variables
- **Error recovery** - Handles migration failures gracefully

### Manual Database Operations (if needed)
```bash
# Check migration status
flask db current

# Create new migration
flask db migrate -m "Description"

# Apply migrations
flask db upgrade

# Reset database (development only)
rm -rf migrations/ && python init_db.py
```

## Health Monitoring

### Health Check Endpoint
```bash
# Check application health
curl http://localhost:5000/health

# Response:
{
  "status": "healthy",
  "database": "connected",
  "application": "running"
}
```

### Docker Health Checks
- Database health monitoring with `pg_isready`
- Web application health via `/health` endpoint
- Automatic restart on health check failures
- Startup dependency management

## User Management

### Admin Access
1. Admin user is automatically created from `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables
2. Login at `/user/login`
3. Access admin features:
   - User management at `/user/admin/users`
   - Invite management at `/user/admin/invites`

### User Invites
- Admins can invite users via email
- Cancelled invites can be reactivated
- Removed users can be invited again
- Email notifications sent automatically

## API Endpoints

### Core Application
- **`GET /`** - Application status
- **`GET /health`** - Health check (returns JSON status)
- **`GET /config`** - Configuration management
- **`POST /sale`** - Process sale transaction
- **`POST /unlinked-refund`** - Process unlinked refund
- **`POST /linked-refund`** - Process linked refund
- **`POST /reversal`** - Process reversal

### User Management
- **`GET /user/login`** - Login page
- **`GET /user/register`** - Registration (invite required)
- **`GET /user/admin/users`** - User management (admin only)
- **`GET /user/admin/invites`** - Invite management (admin only)

### Postbacks
- **`POST /postback`** - Postback receiver endpoint
- **`GET /postbacks`** - View received postbacks

## Data Persistence

### Docker Volumes
- **Database data** - Persistent PostgreSQL data in `pgdata` volume
- **Application data** - Postbacks stored in `./data` directory
- **Development** - Source code mounted for live reload

### File Storage
- Postbacks stored in `/tmp/postbacks.json`
- Daily cleanup of old postback data
- Configuration data in database

## Security Features

- **Environment-based secrets** - No hardcoded credentials
- **Admin role protection** - Admin-only routes properly secured
- **Password hashing** - Secure password storage
- **Session management** - Secure user sessions
- **Input validation** - Request validation and sanitization
- **Sensitive header masking** - Postback display safety

## Troubleshooting

### Database Issues
```bash
# Check database connection
python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.engine.execute('SELECT 1')"

# Reset migrations (development only)
rm -rf migrations/ && python init_db.py

# Check migration status
flask db current && flask db history
```

### Docker Issues
```bash
# Check service health
docker compose ps

# View logs
docker compose logs -f web
docker compose logs -f db

# Debug mode
DEBUG=true docker compose up

# Rebuild containers
docker compose down && docker compose up --build
```

### Application Issues
```bash
# Check health endpoint
curl http://localhost:5000/health

# Check environment variables
docker compose config

# View application logs
docker compose logs -f web
```

## Development

### File Structure
```
├── app/                    # Flask application
│   ├── models/            # Database models
│   ├── routes/            # Route handlers
│   ├── templates/         # HTML templates
│   └── utils/             # Utility functions
├── migrations/            # Database migrations (auto-generated)
├── tests/                 # Test suite
├── init_db.py            # Database initialization script
├── run.py                # Development server launcher
├── entrypoint.sh         # Docker entrypoint
├── .env.example          # Environment variables template
└── docker-compose*.yml   # Docker configurations
```

### Contributing
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Run test suite: `pytest`
5. Submit pull request

## Notes

- **Automatic Setup** - No manual database commands required
- **Production Ready** - Includes health checks and monitoring
- **Development Friendly** - Hot reload and debugging support
- **Secure by Default** - Environment-based configuration
- **Docker Optimized** - Multi-stage builds and health checks

The application is ready to run with standard Flask and Docker commands - no additional setup documentation needed.

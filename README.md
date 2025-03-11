# Terminal Connect Test Application

A Flask application for testing Terminal Connect API integration with support for sales and refunds.

## Setup

### Option 1: Local Setup

1. Create a virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:

   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Generate a secure secret key:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
   - Update `.env` with your configuration:
     - `SECRET_KEY`: The generated secret key
     - `MID`: Your Merchant ID
     - `TID`: Your Terminal ID
     - `API_KEY`: Your Terminal Connect API key
     - `POSTBACK_URL`: Your webhook endpoint for transaction notifications

4. Run the application:

```bash
python app.py
```

### Option 2: Docker Setup

1. Configure environment variables:

   - Copy `.env.example` to `.env` and update the values as described above

2. Build and run with Docker Compose:

```bash
# Build and start the containers
docker-compose up --build

# Run in detached mode (background)
docker-compose up -d

# Stop the containers
docker-compose down
```

The application will be available at `http://localhost:5000`

## Features

- **Configuration Management**

  - Environment selection (Sandbox/Production)
  - MID, TID, and API key configuration
  - Postback URL configuration

- **Transaction Operations**
  - Process sales
  - Process unlinked refunds
  - Process linked refunds (requires parent intent ID)

## Environment Configuration

The application uses the following environment variables:

| Variable     | Description                               | Example                                  |
| ------------ | ----------------------------------------- | ---------------------------------------- |
| SECRET_KEY   | Flask secret key for session management   | `k8AA0aVss_vm/Vaq848KO0v44VoMMzahSvvmtb` |
| MID          | Merchant ID for Terminal Connect          | `12345`                                  |
| TID          | Terminal ID for Terminal Connect          | `WP12345X67890123`                       |
| API_KEY      | API Key for authentication                | `XXXXX-XXXXX-XXXXX-XXXXX`                |
| POSTBACK_URL | Webhook URL for transaction notifications | `https://your-domain.com/webhook`        |

## Security Notes

1. Never commit your `.env` file to version control
2. Keep your API key secure and never share it
3. Use HTTPS for production postback URLs
4. Generate a strong secret key for production use

## Docker Commands

```bash
# Build the image
docker-compose build

# Start the containers
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the containers
docker-compose down

# Remove all containers and volumes
docker-compose down -v
```

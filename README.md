# Terminal Connect Test Application

A Flask application for testing Terminal Connect API integration with support for sales, refunds, reversals, and postback inspection.

## Features

- **Configuration Management**
  - Environment selection (Sandbox/Production)
  - MID, TID, and API key configuration
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

## Setup

### Local Setup

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

   - Copy `.env.example` to `.env` (if provided) or create a `.env` file:
     ```bash
     cp .env.example .env
     ```
   - Update `.env` with your configuration:
     - `SECRET_KEY`: The generated secret key
     - `MID`: Your Merchant ID
     - `TID`: Your Terminal ID
     - `API_KEY`: Your Terminal Connect API key

4. Run the application:

   ```bash
   python app.py
   ```

### Docker Setup

1. Build and run with Docker Compose:

   ```bash
   docker-compose build
   docker-compose up
   ```

   The application will be available at `http://localhost:5001`

2. The Docker image uses `python:3.12-slim` and installs `ca-certificates` for proper SSL support. Python requests are configured to use the system CA bundle for HTTPS.

### Postback Handling

- The application provides a built-in postback endpoint at `/postback` (e.g., `http://localhost:5001/postback`).
- All postbacks received at this endpoint are stored in a local file (cleared daily).
- View all received postbacks at `/postbacks`.
- The postbacks table allows you to expand/collapse details for each postback, with proper line wrapping and masked sensitive headers.

### Security Notes

1. Never commit your `.env` file to version control
2. Keep your API key secure and never share it
3. Use HTTPS for production deployments
4. Generate a strong secret key for production use

### Troubleshooting SSL in Docker

- The Docker image uses the system CA bundle (`/etc/ssl/certs/ca-certificates.crt`) for all outgoing HTTPS requests.
- If you encounter SSL errors, ensure you have rebuilt your Docker image after any changes to the Dockerfile.

### Docker Commands

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

```

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

You have two options for running this application with Docker:

#### 1. Use the Prebuilt Image from GitHub Container Registry

You can use the prebuilt image hosted on GitHub, as configured in the provided `docker-compose.yml`:

```bash
docker-compose up
```

- This will pull the latest image from `ghcr.io/lilyfrank05/terminal-connect-test:latest`.
- No need to build the image yourself.
- The application will be available at `http://localhost:5001`.

#### 2. Build the Image Yourself

If you want to build the image locally (for development or customization), please update the docker compose file accordingly and:

```bash
docker-compose build
docker-compose up
```

#### Environment Variables

- Docker Compose will automatically load environment variables from a `.env` file located in the same directory as your `docker-compose.yml`.
- Create a `.env` file with the following variables:

  ```
  SECRET_KEY=your_secret_key
  MID=your_merchant_id
  TID=your_terminal_id
  API_KEY=your_api_key
  ```

- These variables will be passed into the running container and used by the application.

#### Data Persistence

- The application stores postbacks in a file that is persisted on your host machine in the `./data` directory.
- This ensures postbacks are not lost when the container is restarted.

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

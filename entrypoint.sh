#!/bin/bash
set -e

# Print each command for debugging
set -x

# Ensure the virtualenv/bin is in PATH if needed (for local dev)
export PATH="/home/appuser/.local/bin:$PATH"

echo "Starting Terminal Connect Test application..."

# Function to check if database is ready (basic connectivity)
wait_for_database() {
    echo "Waiting for database to be ready..."
    if [ -n "$DATABASE_URL" ]; then
        # Wait for PostgreSQL to be ready
        until python -c "
import psycopg2
import urllib.parse
import sys
try:
    u = urllib.parse.urlparse('$DATABASE_URL')
    conn = psycopg2.connect(
        host=u.hostname,
        port=u.port or 5432,
        user=u.username,
        password=u.password,
        database=u.path[1:] if u.path else 'postgres'
    )
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
"; do
            echo "Waiting for database to be ready..."
            sleep 2
        done
    else
        echo "No DATABASE_URL provided, assuming SQLite or other configuration"
    fi
}

# Main initialization
main() {
    echo "=== Terminal Connect Test Initialization ==="

    # Step 1: Wait for database to be ready
    wait_for_database

    # Step 2: Run database initialization using Python script
    echo "Running database initialization..."
    if python /app/init_db.py; then
        echo "✓ Database initialization completed successfully"
    else
        echo "✗ Database initialization failed"
        exit 1
    fi

    echo "=== Initialization Complete ==="

    # Debug information (optional, can be removed in production)
    if [ "${DEBUG:-false}" = "true" ]; then
        echo "=== Debug Information ==="
        echo "Working directory: $(pwd)"
        echo "Python path:"
        python -c "import sys; print('\\n'.join(sys.path))" | head -10
        echo "App directory contents:"
        ls -la /app | head -20
        echo "=========================="
    fi

    # Calculate optimal worker count based on CPU cores
    # Default formula: (2 x CPU cores) + 1, with minimum of 2 and maximum of 8
    CPU_COUNT=$(nproc 2>/dev/null || echo 2)
    CALCULATED_WORKERS=$((2 * CPU_COUNT + 1))

    # Apply min/max bounds for safety
    if [ "$CALCULATED_WORKERS" -lt 2 ]; then
        CALCULATED_WORKERS=2
    elif [ "$CALCULATED_WORKERS" -gt 8 ]; then
        CALCULATED_WORKERS=8
    fi

    # Allow environment override
    WORKERS=${GUNICORN_WORKERS:-$CALCULATED_WORKERS}
    WORKER_CLASS=${GUNICORN_WORKER_CLASS:-gthread}
    WORKER_CONNECTIONS=${GUNICORN_WORKER_CONNECTIONS:-1000}
    THREADS=${GUNICORN_THREADS:-4}
    TIMEOUT=${GUNICORN_TIMEOUT:-30}
    MAX_REQUESTS=${GUNICORN_MAX_REQUESTS:-1000}

    echo "=== Gunicorn Configuration ==="
    echo "CPU cores detected: $CPU_COUNT"
    echo "Workers: $WORKERS"
    echo "Worker class: $WORKER_CLASS"
    if [ "$WORKER_CLASS" = "gthread" ]; then
        echo "Threads per worker: $THREADS"
        echo "Total capacity: $((WORKERS * THREADS)) concurrent requests"
    fi
    echo "Worker connections: $WORKER_CONNECTIONS"
    echo "Timeout: $TIMEOUT seconds"
    echo "Max requests per worker: $MAX_REQUESTS"
    echo "=============================="

    echo "Starting Gunicorn server..."
    # Start Gunicorn with optimized configuration
    if [ "$WORKER_CLASS" = "gthread" ]; then
        # Include threads parameter for gthread worker class
        exec gunicorn \
            --chdir /app \
            --bind 0.0.0.0:5000 \
            --workers "$WORKERS" \
            --worker-class "$WORKER_CLASS" \
            --threads "$THREADS" \
            --worker-connections "$WORKER_CONNECTIONS" \
            --max-requests "$MAX_REQUESTS" \
            --max-requests-jitter 100 \
            --timeout "$TIMEOUT" \
            --keep-alive 2 \
            --log-level info \
            --access-logfile - \
            --error-logfile - \
            wsgi:app
    else
        # Original configuration for other worker classes
        exec gunicorn \
            --chdir /app \
            --bind 0.0.0.0:5000 \
            --workers "$WORKERS" \
            --worker-class "$WORKER_CLASS" \
            --worker-connections "$WORKER_CONNECTIONS" \
            --max-requests "$MAX_REQUESTS" \
            --max-requests-jitter 100 \
            --timeout "$TIMEOUT" \
            --keep-alive 2 \
            --log-level info \
            --access-logfile - \
            --error-logfile - \
            wsgi:app
    fi
}

# Run main function
main

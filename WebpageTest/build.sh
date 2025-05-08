#!/bin/bash

# IntelliShop Project Runner
# This script sets up and runs the IntelliShop web application
#
# === USAGE INSTRUCTIONS ===
# How to run:
#   1. Make this script executable: chmod +x build.sh
#   2. Run the script in WSL terminal: ./build.sh [1]
#      - Add "1" parameter to update the database with sample data
#
# How to close:
#   - Press Ctrl+C in the terminal to stop the server
# ===========================

# Logging function with timestamp
log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1"
}

error() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] ERROR: $1" >&2
    exit 1
}

# Global variables for cleanup
SERVER_PID=""
PORT=8000
VENV_DIR=".venv"
PROJECT_DIR="mysite"
ENV_FILE=".env"

# Cleanup function
cleanup() {
    log "Initiating shutdown procedure..."
    
    # Kill Django server process if running
    if [ -n "$SERVER_PID" ]; then
        log "Stopping Django server (PID: $SERVER_PID)"
        kill -TERM $SERVER_PID 2>/dev/null || true
        
        # Wait for process to terminate
        for i in {1..5}; do
            if ! ps -p $SERVER_PID > /dev/null 2>&1; then
                break
            fi
            log "Waiting for server to terminate... ($i/5)"
            sleep 1
        done
        
        # Force kill if still running
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            log "Server still running, forcing termination"
            kill -9 $SERVER_PID 2>/dev/null || true
        fi
    fi
    
    # Check if port is still in use
    if check_port_in_use $PORT; then
        log "Warning: Port $PORT is still in use. Attempting to free it..."
        # Find process using the port and kill it
        pid=$(lsof -t -i:$PORT 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log "Killing process $pid that's using port $PORT"
            kill -9 $pid 2>/dev/null || true
        fi
    fi
    
    # Deactivate virtual environment if active
    if [ -n "$VIRTUAL_ENV" ]; then
        log "Deactivating virtual environment"
        deactivate 2>/dev/null || true
    fi
    
    log "Cleanup complete"
    log "Server shutdown complete"
}

# Check if script is running in a virtual environment
is_in_virtualenv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        return 1  # Not in a virtual environment
    else
        return 0  # In a virtual environment
    fi
}

# MongoDB configuration setup
setup_mongodb_config() {
    log "Setting up MongoDB configuration..."
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log "Creating environment configuration file..."
        cat > "$ENV_FILE" << EOF
# MongoDB Configuration
MONGODB_URI=mongodb+srv://giladshkalim:Gilad1212@intellidb.yuauj7i.mongodb.net/?retryWrites=true&w=majority&appName=IntelliDB
MONGODB_NAME=IntelliDB

# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
EOF
        log "Created environment template at $ENV_FILE"
        log "⚠️  IMPORTANT: Please edit $ENV_FILE with your actual MongoDB credentials"
    else
        log "Environment file $ENV_FILE already exists"
    fi
    
    # Load environment variables
    log "Loading configuration from $ENV_FILE"
    if [ -f "$ENV_FILE" ]; then
        # Export environment variables properly - only export valid variable assignments
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip comments and empty lines
            if [[ $line =~ ^[[:space:]]*# || -z $line ]]; then
                continue
            fi
            
            # Only export if line contains a valid KEY=VALUE format (no spaces around =)
            if [[ $line =~ ^[A-Za-z0-9_]+=.* ]]; then
                export "$line" || log "Warning: Failed to export environment variable: $line"
            else
                log "Warning: Skipping invalid environment variable: $line"
            fi
        done < "$ENV_FILE"
    else
        log "⚠️  $ENV_FILE file not found. MongoDB connection may fail."
    fi
}

# Test MongoDB connection
test_mongodb_connection() {
    log "Testing MongoDB connection..."
    
    # Check if MongoDB URI is set
    if [ -z "$MONGODB_URI" ]; then
        log "⚠️  MongoDB URI not set. Skipping connection test."
        return 1
    fi
    
    # Simple test script
    python3 -c "
from pymongo import MongoClient
import os
import sys

try:
    uri = os.environ.get('MONGODB_URI')
    if not uri:
        print('MongoDB URI not found in environment variables')
        sys.exit(1)
    
    client = MongoClient(uri)
    info = client.server_info()
    print(f'Successfully connected to MongoDB v{info.get(\"version\")}')
    sys.exit(0)
except Exception as e:
    print(f'MongoDB connection error: {e}')
    sys.exit(1)
" && return 0 || return 1
}

# Create necessary MongoDB files
create_mongodb_files() {
    log "Creating MongoDB utility files..."
    
    # Create directories if they don't exist
    mkdir -p "$PROJECT_DIR/intellishop/utils"
    mkdir -p "$PROJECT_DIR/intellishop/models"
    mkdir -p "$PROJECT_DIR/intellishop/management/commands"
    
    # Create mongodb_utils.py
    local MONGODB_UTILS_FILE="$PROJECT_DIR/intellishop/utils/mongodb_utils.py"
    if [ ! -f "$MONGODB_UTILS_FILE" ]; then
        log "Creating MongoDB utility file..."
        cat > "$MONGODB_UTILS_FILE" << 'EOF'
from pymongo import MongoClient
import os

def get_db_handle():
    """
    Returns a handle to the MongoDB database and client
    """
    # Get MongoDB connection details from environment variables or settings
    mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
    db_name = os.environ.get('MONGODB_NAME', 'intellishop_db')
    
    # Create a MongoDB client
    client = MongoClient(mongodb_uri)
    db_handle = client[db_name]
    
    return db_handle, client

def get_collection_handle(collection_name):
    """
    Returns a handle to a specific MongoDB collection
    """
    db, client = get_db_handle()
    return db[collection_name]
EOF
        log "Created MongoDB utility file at $MONGODB_UTILS_FILE"
    else
        log "MongoDB utility file already exists"
    fi
    
    # Create __init__.py files to make directories into packages
    touch "$PROJECT_DIR/intellishop/utils/__init__.py"
    touch "$PROJECT_DIR/intellishop/models/__init__.py"
    
    # Create mongodb_models.py
    local MONGODB_MODELS_FILE="$PROJECT_DIR/intellishop/models/mongodb_models.py"
    if [ ! -f "$MONGODB_MODELS_FILE" ]; then
        log "Creating MongoDB models file..."
        cat > "$MONGODB_MODELS_FILE" << 'EOF'
from bson import ObjectId

class MongoDBModel:
    """Base class for MongoDB models"""
    collection_name = None
    
    @classmethod
    def get_collection(cls):
        """Get the MongoDB collection for this model"""
        from intellishop.utils.mongodb_utils import get_collection_handle
        return get_collection_handle(cls.collection_name)
    
    @classmethod
    def find_one(cls, query):
        """Find a single document"""
        return cls.get_collection().find_one(query)
    
    @classmethod
    def find(cls, query=None, sort=None, limit=None):
        """Find multiple documents"""
        cursor = cls.get_collection().find(query or {})
        
        if sort:
            cursor = cursor.sort(sort)
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    @classmethod
    def insert_one(cls, document):
        """Insert a document into the collection"""
        result = cls.get_collection().insert_one(document)
        return result.inserted_id
    
    @classmethod
    def update_one(cls, query, update):
        """Update a document in the collection"""
        return cls.get_collection().update_one(query, {'$set': update})
    
    @classmethod
    def delete_one(cls, query):
        """Delete a document from the collection"""
        return cls.get_collection().delete_one(query)
EOF
        log "Created MongoDB models file at $MONGODB_MODELS_FILE"
    else
        log "MongoDB models file already exists"
    fi
    
    # Create test command
    mkdir -p "$PROJECT_DIR/intellishop/management/commands"
    touch "$PROJECT_DIR/intellishop/management/__init__.py"
    touch "$PROJECT_DIR/intellishop/management/commands/__init__.py"
    
    local TEST_COMMAND_FILE="$PROJECT_DIR/intellishop/management/commands/test_mongodb.py"
    if [ ! -f "$TEST_COMMAND_FILE" ]; then
        log "Creating MongoDB test command..."
        cat > "$TEST_COMMAND_FILE" << 'EOF'
from django.core.management.base import BaseCommand
from intellishop.utils.mongodb_utils import get_db_handle

class Command(BaseCommand):
    help = 'Test MongoDB connection'

    def handle(self, *args, **options):
        try:
            db, client = get_db_handle()
            server_info = client.server_info()
            self.stdout.write(self.style.SUCCESS(f'Successfully connected to MongoDB version: {server_info["version"]}'))
            self.stdout.write(self.style.SUCCESS(f'Available databases: {client.list_database_names()}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to connect to MongoDB: {e}'))
        finally:
            if 'client' in locals():
                client.close()
EOF
        log "Created MongoDB test command at $TEST_COMMAND_FILE"
    else
        log "MongoDB test command already exists"
    fi
}

# Set up trap for cleanup on script exit
trap cleanup EXIT INT TERM

echo "Checking Python version..."

# Check if Python 3 is installed
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python 3 detected: $PYTHON_VERSION"
else
    echo "❌ Python 3 not detected. Installing Python 3..."
    
    # Detect OS and install Python
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "Detected macOS. Using Homebrew to install Python 3..."
        if command -v brew &>/dev/null; then
            brew install python3
        else
            echo "Homebrew not installed. Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install python3
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "Detected Linux. Installing Python 3..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3 python3-pip
        else
            echo "ERROR: Unsupported package manager. Please install Python 3 manually."
            exit 1
        fi
    else
        echo "ERROR: Unsupported operating system. Please install Python 3 manually."
        exit 1
    fi
    
    # Verify Python was installed
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version)
        echo "✅ Python 3 installed successfully: $PYTHON_VERSION"
    else
        echo "❌ Failed to install Python 3. Please install manually."
        exit 1
    fi
fi

log "Starting IntelliShop setup"

# Configuration
REQUIREMENTS_FILE="requirements.txt"

# If we're already in a virtual environment but not our target one, warn and deactivate
if is_in_virtualenv && [[ "$VIRTUAL_ENV" != *"$VENV_DIR"* ]]; then
    log "Warning: Already in a different virtual environment. Deactivating."
    deactivate 2>/dev/null || true
fi

# Setup or verify virtual environment
if [ -d "$VENV_DIR" ]; then
    log "Virtual environment directory exists, activating"
    source $VENV_DIR/bin/activate || error "Failed to activate existing virtual environment"
    
    # Double-check activation succeeded
    if ! is_in_virtualenv; then
        log "Virtual environment activation failed. Recreating environment."
        rm -rf $VENV_DIR
        python3 -m venv $VENV_DIR || error "Failed to create virtual environment"
        source $VENV_DIR/bin/activate || error "Failed to activate new virtual environment"
    fi
else
    log "Creating new virtual environment"
    python3 -m venv $VENV_DIR || error "Failed to create virtual environment"
    source $VENV_DIR/bin/activate || error "Failed to activate new virtual environment"
fi

# Verify we're now in a virtual environment
if ! is_in_virtualenv; then
    error "Failed to properly activate virtual environment"
fi

log "Successfully activated virtual environment: $VIRTUAL_ENV"

# Update pip to latest version
log "Updating pip to latest version"
python -m pip install --upgrade pip || log "Warning: Failed to upgrade pip"

# Install dependencies from requirements file if it exists
if [ -f "$REQUIREMENTS_FILE" ]; then
    log "Installing dependencies from $REQUIREMENTS_FILE"
    python -m pip install -r $REQUIREMENTS_FILE || error "Failed to install requirements"
else
    # Install Django if not already installed
    if ! python -m pip show django &> /dev/null; then
        log "Installing Django"
        python -m pip install django || error "Failed to install Django"
    else
        log "Django already installed in virtual environment"
    fi
    
    # Install MongoDB dependencies
    log "Installing PyMongo and dnspython"
    python -m pip install pymongo dnspython || log "Warning: Failed to install MongoDB dependencies"
fi

# Set up MongoDB configuration
setup_mongodb_config

# Create MongoDB utility files
create_mongodb_files

# Change to the Django project directory
if [ ! -d "$PROJECT_DIR" ]; then
    error "Django project directory '$PROJECT_DIR' not found"
fi

cd $PROJECT_DIR || error "Failed to change to project directory"

# Test MongoDB connection
test_mongodb_connection || log "Warning: MongoDB connection test failed. The application may not function correctly."

# Check if port is already in use
if check_port_in_use $PORT; then
    log "Warning: Port $PORT is already in use"
    pid=$(lsof -i:$PORT 2>/dev/null || true)
    if [ -n "$pid" ]; then
        log "Process $pid is using port $PORT"
        read -p "Do you want to kill this process and free the port? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Killing process $pid"
            kill -9 $pid || log "Failed to kill process $pid"
            sleep 2
        else
            error "Port $PORT is in use. Please free the port or use a different one."
        fi
    fi
fi

# Run database migrations if needed
log "Running database migrations"
python manage.py migrate || log "Warning: Database migration failed"

# Collect static files for production
log "Collecting static files"
python manage.py collectstatic --noinput || log "Warning: Static file collection failed"

# Check for Django configuration errors
log "Checking for configuration errors"
python manage.py check --deploy || log "Warning: Django deployment checks failed"

# Check if database update was requested
if [ "$1" = "1" ]; then
    log "Database update requested. Running update script..."
    python update_database.py
    if [ $? -ne 0 ]; then
        log "⚠️ Database update failed!"
    else
        log "✅ Database updated successfully!"
    fi
else
    log "Skipping database update. Run with './build.sh 1' to update the database."
fi

# Start the Django development server
log "Please wait for Django to start on port $PORT"

# Run Django server in background so we can capture its PID
python manage.py runserver 0.0.0.0:$PORT &
SERVER_PID=$!

log "Server running with PID: $SERVER_PID"

# Wait for the Django server to exit
wait $SERVER_PID 2>/dev/null || true

# The cleanup function will be called automatically through the trap 

# Add this function near the top of the script
check_port_in_use() {
    local port=$1
    
    # Try different commands based on what's available
    if command -v netstat &>/dev/null; then
        netstat -tuln | grep ":$port " > /dev/null 2>&1
        return $?
    elif command -v ss &>/dev/null; then
        ss -tuln | grep ":$port " > /dev/null 2>&1
        return $?
    elif command -v lsof &>/dev/null; then
        lsof -i :$port > /dev/null 2>&1
        return $?
    else
        # If no tool is available, we can't check - assume it's not in use
        log "Warning: Cannot check if port is in use (netstat, ss, and lsof not found)"
        return 1
    fi
} 
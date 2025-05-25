#!/bin/bash

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SH="$SCRIPT_DIR/common.sh"

if [ -f "$COMMON_SH" ]; then
    source "$COMMON_SH"
else
    echo "$(date +%Y-%m-%d\ %H:%M:%S,%3N) - Build - ERROR - Common utilities file not found: $COMMON_SH" >&2
    exit 1
fi

# Script variables
VENV_DIR="venv"
PROJECT_DIR="mysite"
ABSOLUTE_ENV_FILE="$SCRIPT_DIR/.env"
ENV_FILE=".env"
SCRIPT_NAME="Build"
LOG_LEVEL=${LOG_LEVEL:-1}  # Default to INFO level (1)

# ===== Helper Functions =====

cleanup() {
    log "Cleaning up resources" 1 "$SCRIPT_NAME"
    
    # Kill any remaining background processes
    for job in $(jobs -p); do
        log "Killing background process $job" 2 "$SCRIPT_NAME"
        kill $job 2>/dev/null || true
    done
    
    # If we're in a virtual environment, deactivate it
    if is_in_virtualenv; then
        deactivate 2>/dev/null || true
        log "Deactivated virtual environment" 1 "$SCRIPT_NAME"
    fi
    
    # If this was called due to an interrupt, exit the script
    if [ "${1:-}" = "INT" ]; then
        log "Script interrupted by user" 1 "$SCRIPT_NAME"
        # Use exit code 130 which is the standard for Ctrl+C interruption
        exit 130
    fi
}

# ===== MongoDB Functions =====

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
ALLOWED_HOSTS=localhost,127.0.0.1
EOF
        log "Created environment template at $ENV_FILE"
    fi
    
    # Load environment variables
    source "$ENV_FILE"
}

# Test MongoDB connection
test_mongodb_connection() {
    log "Testing MongoDB connection..." 1 "$SCRIPT_NAME"
    
    # Check if MongoDB URI is set
    if [ -z "$MONGODB_URI" ]; then
        log "⚠️  MongoDB URI not set. Skipping connection test." 0 "$SCRIPT_NAME"
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
    log "Creating MongoDB utility files..." 1 "$SCRIPT_NAME"
    
    # Create directories if they don't exist
    mkdir -p "$PROJECT_DIR/intellishop/utils"
    mkdir -p "$PROJECT_DIR/intellishop/models"
    mkdir -p "$PROJECT_DIR/intellishop/management/commands"
    
    # Create mongodb_utils.py
    local MONGODB_UTILS_FILE="$PROJECT_DIR/intellishop/utils/mongodb_utils.py"
    if [ ! -f "$MONGODB_UTILS_FILE" ]; then
        log "Creating MongoDB utility file..." 1 "$SCRIPT_NAME"
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
        log "Created MongoDB utility file at $MONGODB_UTILS_FILE" 1 "$SCRIPT_NAME"
    else
        log "MongoDB utility file already exists" 1 "$SCRIPT_NAME"
    fi
    
    # Create __init__.py files to make directories into packages
    touch "$PROJECT_DIR/intellishop/utils/__init__.py"
    touch "$PROJECT_DIR/intellishop/models/__init__.py"
    
    # Create mongodb_models.py
    local MONGODB_MODELS_FILE="$PROJECT_DIR/intellishop/models/mongodb_models.py"
    if [ ! -f "$MONGODB_MODELS_FILE" ]; then
        log "Creating MongoDB models file..." 1 "$SCRIPT_NAME"
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
        log "Created MongoDB models file at $MONGODB_MODELS_FILE" 1 "$SCRIPT_NAME"
    else
        log "MongoDB models file already exists" 1 "$SCRIPT_NAME"
    fi
    
    # Create test command
    mkdir -p "$PROJECT_DIR/intellishop/management/commands"
    touch "$PROJECT_DIR/intellishop/management/__init__.py"
    touch "$PROJECT_DIR/intellishop/management/commands/__init__.py"
    
    local TEST_COMMAND_FILE="$PROJECT_DIR/intellishop/management/commands/test_mongodb.py"
    if [ ! -f "$TEST_COMMAND_FILE" ]; then
        log "Creating MongoDB test command..." 1 "$SCRIPT_NAME"
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
        log "Created MongoDB test command at $TEST_COMMAND_FILE" 1 "$SCRIPT_NAME"
    else
        log "MongoDB test command already exists" 1 "$SCRIPT_NAME"
    fi
}

# Groq API Enhancement Functions
verify_api_key() {
    log "Verifying Groq API key..." 1 "$SCRIPT_NAME"
    
    # Check if .env file exists
    if [ ! -f "$ABSOLUTE_ENV_FILE" ]; then
        log "❌ $ABSOLUTE_ENV_FILE file not found." 0 "$SCRIPT_NAME"
        log "Creating template .env file..." 1 "$SCRIPT_NAME"
        
        # Create template .env file
        cat > "$ABSOLUTE_ENV_FILE" << EOF
GROQ_API_KEY=your_api_key_here
EOF
        
        error "Please update the .env file with your actual Groq API key and run again." "$SCRIPT_NAME"
    fi
    
    # Load and check API key
    source "$ABSOLUTE_ENV_FILE" 2>/dev/null
    
    if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "your_api_key_here" ]; then
        error "Invalid or missing Groq API key in $ABSOLUTE_ENV_FILE. Please update it." "$SCRIPT_NAME"
    fi
    
    log "✅ Groq API key found." 1 "$SCRIPT_NAME"
}

validate_script() {
    local SCRIPT_FILE="$1"
    
    if [ ! -f "$SCRIPT_FILE" ]; then
        error "Script file $SCRIPT_FILE not found in $(pwd). Please check the file path." "$SCRIPT_NAME"
    fi
    
    log "✅ Script validation passed." 1 "$SCRIPT_NAME"
}

run_enhancement_process() {
    local SCRIPT_FILE="$1"
    
    # Run the script
    log "Starting data enhancement process..." 1 "$SCRIPT_NAME"

    python "$SCRIPT_FILE" &
    local ENHANCEMENT_PID=$!

    log "Process running with PID: $ENHANCEMENT_PID" 2 "$SCRIPT_NAME"

    # Wait for the script to complete
    wait $ENHANCEMENT_PID 2>/dev/null
    local EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        log "✅ Enhancement process completed successfully!" 1 "$SCRIPT_NAME"
        log "Enhanced files have been saved in the data directory." 1 "$SCRIPT_NAME"
    else
        log "❌ Enhancement process failed with exit code $EXIT_CODE." 0 "$SCRIPT_NAME"
    fi
}

# Add port checking function if it's not already in common.sh
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
        log "Warning: Cannot check if port is in use (netstat, ss, and lsof not found)" 0 "$SCRIPT_NAME"
        return 1
    fi
}

# Set up trap for cleanup on script exit - pass the signal type to cleanup
trap 'cleanup EXIT' EXIT
trap 'cleanup INT' INT
trap 'cleanup TERM' TERM

# ===== Main Script =====

log "Checking Python version..." 1 "$SCRIPT_NAME"

# Check if Python 3 is installed
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version)
    log "✅ Python 3 detected: $PYTHON_VERSION" 1 "$SCRIPT_NAME"
else
    log "❌ Python 3 not detected. Installing Python 3..." 0 "$SCRIPT_NAME"
    
    # Detect OS and install Python
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        log "Detected macOS. Using Homebrew to install Python 3..." 1 "$SCRIPT_NAME"
        if command -v brew &>/dev/null; then
            brew install python3
        else
            log "Homebrew not installed. Installing Homebrew first..." 1 "$SCRIPT_NAME"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install python3
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        log "Detected Linux. Installing Python 3..." 1 "$SCRIPT_NAME"
        if command -v apt-get &>/dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3 python3-pip
        else
            error "Unsupported package manager. Please install Python 3 manually." "$SCRIPT_NAME"
        fi
    else
        error "Unsupported operating system. Please install Python 3 manually." "$SCRIPT_NAME"
    fi
    
    # Verify Python was installed
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version)
        log "✅ Python 3 installed successfully: $PYTHON_VERSION" 1 "$SCRIPT_NAME"
    else
        error "Failed to install Python 3. Please install manually." "$SCRIPT_NAME"
    fi
fi

log "Starting IntelliShop setup" 1 "$SCRIPT_NAME"

# Configuration
REQUIREMENTS_FILE="requirements.txt"

# Setup virtual environment using function from common.sh
setup_virtual_environment "$VENV_DIR"

log "Successfully activated virtual environment: $VIRTUAL_ENV" 1 "$SCRIPT_NAME"

# Update pip to latest version
log "Updating pip to latest version" 1 "$SCRIPT_NAME"
python -m pip install --upgrade pip > /dev/null 2>&1 &
PIP_PID=$!
show_progress_bar $PIP_PID "Updating pip"
wait $PIP_PID
if [ $? -ne 0 ]; then
    log "Warning: Failed to upgrade pip" 0 "$SCRIPT_NAME"
fi

# Install dependencies from requirements file if it exists
if [ -f "$REQUIREMENTS_FILE" ]; then
    log "Installing dependencies from $REQUIREMENTS_FILE" 1 "$SCRIPT_NAME"
    python -m pip install -r $REQUIREMENTS_FILE > /dev/null 2>&1 &
    PIP_PID=$!
    show_progress_bar $PIP_PID "Installing dependencies"
    wait $PIP_PID
    if [ $? -ne 0 ]; then
        error "Failed to install requirements" "$SCRIPT_NAME"
    fi
else
    # Install Django if not already installed
    if ! python -m pip show django &> /dev/null; then
        log "Installing Django" 1 "$SCRIPT_NAME"
        python -m pip install django > /dev/null 2>&1 &
        PIP_PID=$!
        show_progress_bar $PIP_PID "Installing Django"
        wait $PIP_PID
        if [ $? -ne 0 ]; then
            error "Failed to install Django" "$SCRIPT_NAME"
        fi
    else
        log "Django already installed in virtual environment" 1 "$SCRIPT_NAME"
    fi
    
    # Install MongoDB dependencies
    log "Installing PyMongo and dnspython" 1 "$SCRIPT_NAME"
    python -m pip install pymongo dnspython > /dev/null 2>&1 &
    PIP_PID=$!
    show_progress_bar $PIP_PID "Installing MongoDB dependencies"
    wait $PIP_PID
    if [ $? -ne 0 ]; then
        log "Warning: Failed to install MongoDB dependencies" 0 "$SCRIPT_NAME"
    fi
fi

# Set up MongoDB configuration
setup_mongodb_config

# Create MongoDB utility files
create_mongodb_files

# Change to the Django project directory
if [ ! -d "$PROJECT_DIR" ]; then
    error "Django project directory '$PROJECT_DIR' not found" "$SCRIPT_NAME"
fi

cd $PROJECT_DIR || error "Failed to change to project directory" "$SCRIPT_NAME"

# Test MongoDB connection
test_mongodb_connection || log "Warning: MongoDB connection test failed. The application may not function correctly." 0 "$SCRIPT_NAME"

# Run database migrations if needed
log "Running database migrations" 1 "$SCRIPT_NAME"
python manage.py migrate || log "Warning: Database migration failed" 0 "$SCRIPT_NAME"

# Collect static files for production
log "Collecting static files" 1 "$SCRIPT_NAME"
python manage.py collectstatic --noinput || log "Warning: Static file collection failed" 0 "$SCRIPT_NAME"

# Check for Django configuration errors
log "Checking for configuration errors" 1 "$SCRIPT_NAME"
python manage.py check --deploy || log "Warning: Django deployment checks failed" 0 "$SCRIPT_NAME"

# Check if database update was requested
if [ "$1" = "1" ]; then
    log "Database update requested. Running update script..." 1 "$SCRIPT_NAME"
    python update_database.py
    if [ $? -ne 0 ]; then
        log "⚠️ Database update failed!" 0 "$SCRIPT_NAME"
    else
        log "✅ Database updated successfully!" 1 "$SCRIPT_NAME"
    fi
elif [ "$1" = "2" ]; then
    # Define Groq-specific variables
    GROQ_SCRIPT_FILE="groq_chat.py"
    GROQ_REQUIREMENTS_FILE="requirements.txt"
    
    log "Running AI enhancement process..." 1 "$SCRIPT_NAME"
    
    # Verify the Groq API key
    verify_api_key
    
    # Validate script files
    validate_script "$GROQ_SCRIPT_FILE" "$GROQ_REQUIREMENTS_FILE"
    
    # Run the enhancement process
    run_enhancement_process "$GROQ_SCRIPT_FILE"
    
    # Then run the database update script
    log "Running database update script..." 1 "$SCRIPT_NAME"
    python update_database.py
    if [ $? -ne 0 ]; then
        log "⚠️ Database update failed!" 0 "$SCRIPT_NAME"
    else
        log "✅ Database updated successfully!" 1 "$SCRIPT_NAME"
    fi
else
    log "Skipping database update. Run with './build.sh 1' to update the database or './build.sh 2' for AI enhancement and database update." 1 "$SCRIPT_NAME"
fi

# Print final summary
log "==== Build Process Summary ====" 1 "$SCRIPT_NAME"
log "✅ Python environment: $PYTHON_VERSION" 1 "$SCRIPT_NAME"
log "✅ Virtual environment: Activated in $VENV_DIR" 1 "$SCRIPT_NAME"
log "✅ Django project: Ready in $PROJECT_DIR" 1 "$SCRIPT_NAME"

if [ "$1" = "1" ]; then
    log "✅ Database: Updated" 1 "$SCRIPT_NAME"
elif [ "$1" = "2" ]; then
    log "✅ AI Enhancement: Completed" 1 "$SCRIPT_NAME"
    log "✅ Database: Updated" 1 "$SCRIPT_NAME"
else
    log "ℹ️ Database: Not updated (use './build.sh 1' or './build.sh 2' to update)" 1 "$SCRIPT_NAME"
fi

log "Build process completed successfully!" 1 "$SCRIPT_NAME"

# Start Django server section
PORT=8000

# Check if port is already in use
if check_port_in_use $PORT; then
    log "Warning: Port $PORT is already in use" 0 "$SCRIPT_NAME"
    # Get the process ID using the port
    if command -v lsof &>/dev/null; then
        pid=$(lsof -t -i:$PORT 2>/dev/null || true)
    elif command -v netstat &>/dev/null && command -v grep &>/dev/null && command -v awk &>/dev/null; then
        pid=$(netstat -nlp 2>/dev/null | grep ":$PORT " | awk '{print $7}' | cut -d'/' -f1)
    fi
    
    if [ -n "$pid" ]; then
        log "Process $pid is using port $PORT" 0 "$SCRIPT_NAME"
        read -p "Do you want to kill this process and free the port? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Killing process $pid" 1 "$SCRIPT_NAME"
            kill -9 $pid || log "Failed to kill process $pid" 0 "$SCRIPT_NAME"
            sleep 2
        else
            error "Port $PORT is in use. Please free the port or use a different one." "$SCRIPT_NAME"
        fi
    fi
fi

# Before starting server, remove the automatic cleanup traps
trap - EXIT 
trap - TERM

# Only clean up on explicit interrupt (Ctrl+C)
trap 'log "Caught interrupt signal. Shutting down server..." 1 "$SCRIPT_NAME"; cleanup INT' INT

# Improve server startup with clear error messages
start_django_server() {
    log "Starting Django server on port $PORT"
    # Check for pending migrations first
    python manage.py makemigrations --check
    python manage.py migrate
    
    # Start the server with verbose output to catch errors
    python manage.py runserver 0.0.0.0:$PORT --traceback
}

# Add this near the end of your script, replacing the existing server start code
start_django_server

# Only run cleanup if we get here (server explicitly stopped)
cleanup

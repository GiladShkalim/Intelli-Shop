#!/usr/bin/env python
"""
Database Update Script for IntelliShop

This script updates the MongoDB database with sample data from JSON and CSV files.
It should be run after build.sh when passing the parameter "1".
"""

import os
import sys
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
import pymongo

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DatabaseUpdate")

# Add the project directory to the path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'mysite'))

# Try to import Django settings
try:
    import django
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    django.setup()
    
    # Import models after Django setup
    from intellishop.models.mongodb_models import Coupon, User
    from intellishop.utils.mongodb_utils import get_db_handle, get_collection_handle
except ImportError as e:
    logger.error(f"Failed to import Django modules: {e}")
    sys.exit(1)

class DatabaseManager:
    _instance = None
    _db = None
    _client = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance
    
    def initialize(self):
        if self._client is None:
            # Connect to MongoDB
            uri = os.getenv('MONGODB_URI')
            if not uri:
                raise ValueError("MongoDB URI not configured")
            
            self._client = pymongo.MongoClient(uri)
            self._db = self._client[os.getenv('MONGODB_NAME', 'IntelliDB')]
        return self._db

def test_mongodb_connection():
    """Test the MongoDB connection before proceeding"""
    try:
        db = DatabaseManager.get_instance().initialize()
        server_info = db.client.server_info()
        logger.info(f"Successfully connected to MongoDB version: {server_info['version']}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

def find_data_files():
    """Find all JSON and CSV files in the data directory and its subdirectories"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'mysite', 'intellishop', 'data')
    
    # Add fallback paths if the primary one doesn't exist
    if not os.path.exists(data_dir):
        alternative_paths = [
            os.path.join(base_dir, 'intellishop', 'data'),
            os.path.join(base_dir, 'mysite', 'data')
        ]
        
        for alt_path in alternative_paths:
            if os.path.exists(alt_path):
                data_dir = alt_path
                logger.info(f"Using alternative data directory: {data_dir}")
                break
    
    json_files = []
    csv_files = []
    
    if not os.path.exists(data_dir):
        logger.warning(f"Data directory not found: {data_dir}")
        return json_files, csv_files
    
    logger.info(f"Scanning for data files in {data_dir}")
    
    # Walk through directory and its subdirectories
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if file.lower().endswith('.json'):
                json_files.append(file_path)
            elif file.lower().endswith('.csv'):
                csv_files.append(file_path)
    
    logger.info(f"Found {len(json_files)} JSON files and {len(csv_files)} CSV files")
    
    return json_files, csv_files

def process_coupon_data(coupon_data):
    """Custom pre-validation processing for coupon data"""
    # Normalize data fields
    if 'code' in coupon_data:
        coupon_data['code'] = coupon_data['code'].strip().upper()
    
    # Add computed fields
    if 'date_created' not in coupon_data:
        coupon_data['date_created'] = datetime.now().isoformat()
    
    # Add business logic validations
    if coupon_data.get('discount_type') == 'percent' and coupon_data.get('amount', 0) > 50:
        logger.warning(f"High discount detected: {coupon_data['code']} with {coupon_data['amount']}%")
    
    return coupon_data

def import_json_file(file_path):
    """Import data from a JSON file"""
    try:
        logger.info(f"Importing data from JSON file: {file_path}")
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Determine type of data based on file name or content
            if 'coupon_samples.json' in file_path:
                # Handle coupon data specifically
                results = Coupon.import_from_json(data)
                logger.info(f"Imported coupon data: {results['valid']} valid, {results['invalid']} invalid")
                return True
            else:
                # Look for array of objects with identifiable fields
                if isinstance(data, list) and len(data) > 0:
                    sample = data[0]
                    if 'title' in sample and ('price' in sample or 'price_type' in sample or 'coupon_code' in sample):
                        results = Coupon.import_from_json(data)
                        logger.info(f"Imported as coupon data: {results['valid']} valid, {results['invalid']} invalid")
                        return True
                
                logger.warning(f"Unknown data format in {file_path}. Skipping.")
                return False
    except Exception as e:
        logger.error(f"Error importing JSON file {file_path}: {str(e)}")
        return False

def import_csv_file(file_path):
    """Import data from a CSV file"""
    try:
        logger.info(f"Importing data from CSV file: {file_path}")
        
        # First try to determine the file type by name
        if 'sample_offers.csv' in file_path or 'coupons' in file_path.lower():
            with open(file_path, 'r', encoding='utf-8') as f:
                # Add more detailed logging to debug import issues
                logger.info(f"Starting CSV import from {file_path}")
                results = Coupon.import_from_csv(f)
                if results['invalid'] > 0:
                    for error in results.get('errors', []):
                        logger.warning(f"CSV import error: {error}")
                logger.info(f"Imported coupon data: {results['valid']} valid, {results['invalid']} invalid")
            return True
        else:
            # Try to determine type by reading headers
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                
                if headers:
                    # Log the headers we found
                    logger.info(f"CSV headers found: {', '.join(headers)}")
                    
                    # Check if headers match coupon fields - use both naming conventions
                    coupon_fields = ['title', 'price', 'coupon_code', 'price_type', 'discount_type', 'valid_until']
                    matches = sum(1 for field in coupon_fields if field in headers)
                    
                    logger.info(f"Found {matches} matching coupon fields in CSV headers")
                    
                    if matches >= 3:  # If at least 3 coupon fields match
                        f.seek(0)  # Reset file pointer to beginning
                        logger.info("CSV file appears to contain coupon data, importing...")
                        results = Coupon.import_from_csv(f)
                        
                        # Log detailed error information
                        if results['invalid'] > 0:
                            for error in results.get('errors', []):
                                logger.warning(f"CSV import error: {error}")
                                
                        logger.info(f"Imported as coupon data: {results['valid']} valid, {results['invalid']} invalid")
                        return True
            
            logger.warning(f"Unknown CSV format in {file_path}. Skipping.")
            return False
    except Exception as e:
        logger.error(f"Error importing CSV file {file_path}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def verify_database_content():
    """Verify that the database was updated successfully"""
    try:
        # Count documents in collections
        current_date = datetime.now()
        
        logger.info("Verifying database content...")
        
        # Check coupon collection
        active_coupons = 0
        expired_coupons = 0
        
        coupons_collection = get_collection_handle('coupons')
        if coupons_collection is not None:  # Properly check for None
            active_coupons = coupons_collection.count_documents({
                '$or': [
                    {'valid_until': {'$gt': current_date}},
                    {'valid_until': None}
                ]
            })
            
            expired_coupons = coupons_collection.count_documents({
                'valid_until': {'$lte': current_date}
            })
        else:
            logger.error("Could not get coupons collection handle")
            return False
        
        logger.info(f"Coupon stats: {active_coupons} active, {expired_coupons} expired")
        return True
    except Exception as e:
        logger.error(f"Error verifying database content: {str(e)}")
        return False

def main():
    """Main function to update the database"""
    logger.info("Starting database update process")
    
    # Test MongoDB connection
    if not test_mongodb_connection():
        logger.error("MongoDB connection test failed. Aborting update.")
        return False
    
    # Find all data files
    json_files, csv_files = find_data_files()
    
    if not json_files and not csv_files:
        logger.warning("No data files found to import. Check your data directory structure.")
        return False
    
    # Process all JSON files
    json_success = True
    for json_file in json_files:
        file_result = import_json_file(json_file)
        json_success = json_success and file_result
    
    # Process all CSV files
    csv_success = True
    for csv_file in csv_files:
        file_result = import_csv_file(csv_file)
        csv_success = csv_success and file_result
    
    # Verify database content
    verify_result = verify_database_content()
    
    if json_success and csv_success and verify_result:
        logger.info("✅ Database update completed successfully!")
        return True
    else:
        logger.warning("⚠️ Database update completed with warnings or errors.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

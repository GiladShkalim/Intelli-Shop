from django.core.management.base import BaseCommand, CommandError
from intellishop.models.mongodb_models import Coupon
from django.conf import settings
import os
import json
import logging
import shutil

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import coupons from JSON or CSV files'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, nargs='?', help='Path to the JSON or CSV file containing coupon data')
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing coupons before importing',
        )
        parser.add_argument(
            '--sample',
            choices=['json', 'csv', 'all'],
            help='Import sample data files from intellishop/data/coupons/',
        )

    def handle(self, *args, **options):
        clear = options.get('clear', False)
        file_path = options.get('file_path')
        sample = options.get('sample')
        
        # Handle sample data import
        if sample:
            base_dir = settings.BASE_DIR
            
            # Clear existing coupons if requested
            if clear:
                self._clear_coupons()
            
            if sample == 'json' or sample == 'all':
                json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'coupon_samples.json')
                if os.path.exists(json_path):
                    self.stdout.write(f"Importing JSON sample from: {json_path}")
                    self._import_from_file(json_path)
                else:
                    self.stdout.write(self.style.WARNING(f"JSON sample file not found at: {json_path}"))
                
            if sample == 'csv' or sample == 'all':
                csv_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'sample_offers.csv')
                if os.path.exists(csv_path):
                    self.stdout.write(f"Importing CSV sample from: {csv_path}")
                    self._import_from_file(csv_path)
                else:
                    self.stdout.write(self.style.WARNING(f"CSV sample file not found at: {csv_path}"))
                
            return
        
        # Regular file import
        if not file_path:
            self.stdout.write(self.style.ERROR("Error: file_path is required"))
            self.stdout.write("Use --sample json|csv|all to import sample data")
            return
            
        # Check if file exists
        if not os.path.exists(file_path):
            raise CommandError(f'File does not exist: {file_path}')
        
        # Clear existing coupons if requested
        if clear:
            self._clear_coupons()
        
        # Import coupons from file
        self._import_from_file(file_path)
    
    def _clear_coupons(self):
        """Clear all existing coupons from the collection"""
        collection = Coupon.get_collection()
        if collection is not None:
            try:
                result = collection.delete_many({})
                self.stdout.write(self.style.SUCCESS(f'Deleted {result.deleted_count} existing coupons'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error clearing coupons: {str(e)}'))
        else:
            self.stdout.write(self.style.ERROR('Could not access coupons collection'))
    
    def _import_from_file(self, file_path):
        """Import coupons from a file (JSON or CSV)"""
        # Import coupons based on file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        results = None
        if file_ext == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                results = Coupon.import_from_json(json_data)
            except Exception as e:
                raise CommandError(f'Error importing coupons from JSON: {str(e)}')
        elif file_ext == '.csv':
            try:
                results = Coupon.import_from_csv(file_path)
            except Exception as e:
                raise CommandError(f'Error importing coupons from CSV: {str(e)}')
        else:
            raise CommandError(f'Unsupported file type: {file_ext}. Please use JSON or CSV files.')
        
        # Display results
        if results:
            self.stdout.write(self.style.SUCCESS(f'Processed {results["total"]} coupons:'))
            self.stdout.write(f'  Valid: {results["valid"]}')
            self.stdout.write(f'  Invalid: {results["invalid"]}')
            self.stdout.write(f'  Updated: {results.get("updated", 0)}')
            self.stdout.write(f'  New: {results.get("new", 0)}')
            
            if results["errors"]:
                self.stdout.write(self.style.WARNING('\nErrors:'))
                for error in results["errors"][:10]:  # Show only first 10 errors
                    self.stdout.write(f'  - {error}')
                
                if len(results["errors"]) > 10:
                    self.stdout.write(f'  ... and {len(results["errors"]) - 10} more errors')
    
    def get_available_files(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.join(base_dir, 'intellishop', 'data')
        
        # Add fallback paths
        if not os.path.exists(data_dir):
            alternative_paths = [
                os.path.join(base_dir, 'data'),
                os.path.join(os.path.dirname(base_dir), 'intellishop', 'data')
            ]
            
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    data_dir = alt_path
                    self.stdout.write(f"Using alternative data directory: {data_dir}")
                    break
        
        available_files = []
        
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                if file.endswith('.json') or file.endswith('.csv'):
                    available_files.append(os.path.join(data_dir, file))
        
        return available_files 

def ensure_data_directory():
    """
    Ensures that the data directory exists with the required structure.
    Creates it if it doesn't exist.
    """
    # Get the base path of the intellishop application
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    
    # Create the data directory if it doesn't exist
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Created data directory: {data_dir}")
        except Exception as e:
            logger.error(f"Failed to create data directory: {e}")
            return False
    
    # Check if sample files exist in the data directory
    sample_files_missing = True
    for filename in ['sample_offers.csv', 'coupon_samples.json']:
        if os.path.exists(os.path.join(data_dir, filename)):
            sample_files_missing = False
            break
    
    # If sample files are missing, try to copy them from distribution
    if sample_files_missing:
        try:
            # Try different possible locations
            potential_sources = [
                # From project root
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(base_dir))), 'data'),
                # From Django project root
                os.path.join(os.path.dirname(base_dir), 'data'),
                # From current working directory
                os.path.join(os.getcwd(), 'data')
            ]
            
            for source_dir in potential_sources:
                if os.path.exists(source_dir):
                    for filename in os.listdir(source_dir):
                        if filename.endswith('.json') or filename.endswith('.csv'):
                            src_file = os.path.join(source_dir, filename)
                            dst_file = os.path.join(data_dir, filename)
                            shutil.copy2(src_file, dst_file)
                            logger.info(f"Copied sample file from {src_file} to {dst_file}")
                    break
        except Exception as e:
            logger.error(f"Failed to copy sample files: {e}")
    
    return os.path.exists(data_dir)
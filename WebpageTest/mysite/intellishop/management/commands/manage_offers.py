from django.core.management.base import BaseCommand, CommandError
from intellishop.models.mongodb_models import Coupon
import os
import json
import csv
import datetime
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manage offers/coupons in the database (import, update, remove, list)'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Import command
        import_parser = subparsers.add_parser('import', help='Import offers from a file')
        import_parser.add_argument('file_path', type=str, nargs='?', help='Path to the JSON or CSV file containing offer data')
        import_parser.add_argument('--update', action='store_true', help='Update existing offers instead of skipping them')
        import_parser.add_argument('--clear', action='store_true', help='Clear existing offers before importing')
        import_parser.add_argument('--sample', choices=['json', 'csv', 'all'], 
                                  help='Use sample data files (json, csv, or all)')
        
        # Remove command
        remove_parser = subparsers.add_parser('remove', help='Remove offers')
        remove_parser.add_argument('--code', type=str, help='Remove an offer by its code')
        remove_parser.add_argument('--expired', action='store_true', help='Remove all expired offers')
        remove_parser.add_argument('--all', action='store_true', help='Remove all offers')
        
        # List command
        list_parser = subparsers.add_parser('list', help='List offers')
        list_parser.add_argument('--active', action='store_true', help='Show only active (non-expired) offers')
        list_parser.add_argument('--expired', action='store_true', help='Show only expired offers')
        list_parser.add_argument('--code', type=str, help='Filter offers by code (supports partial matching)')
        list_parser.add_argument('--min-amount', type=float, help='Filter offers by minimum amount')
        list_parser.add_argument('--max-amount', type=float, help='Filter offers by maximum amount')
        list_parser.add_argument('--type', type=str, choices=['percent', 'fixed_cart', 'fixed_product'], 
                                help='Filter offers by discount type')
        list_parser.add_argument('--format', type=str, choices=['table', 'json'], default='table',
                                help='Output format (table or json)')

    def handle(self, *args, **options):
        command = options.get('command')
        
        if not command:
            self.print_help('manage.py', 'manage_offers')
            return
            
        # Execute the appropriate command
        if command == 'import':
            # Check if sample option is specified
            sample_type = options.get('sample')
            if sample_type:
                # Import sample data
                base_dir = settings.BASE_DIR
                
                if sample_type == 'json' or sample_type == 'all':
                    json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'coupon_samples.json')
                    if os.path.exists(json_path):
                        self.stdout.write(f"Importing JSON sample from: {json_path}")
                        options['file_path'] = json_path
                        self.import_offers(options)
                    else:
                        self.stdout.write(self.style.WARNING(f"JSON sample file not found at: {json_path}"))
                
                if sample_type == 'csv' or sample_type == 'all':
                    csv_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'sample_offers.csv')
                    if os.path.exists(csv_path):
                        self.stdout.write(f"Importing CSV sample from: {csv_path}")
                        options['file_path'] = csv_path
                        self.import_offers(options)
                    else:
                        self.stdout.write(self.style.WARNING(f"CSV sample file not found at: {csv_path}"))
                
                return
            
            # If no file_path is provided, show help
            if 'file_path' not in options or not options['file_path']:
                self.stdout.write(self.style.ERROR("Error: file_path is required"))
                self.stdout.write("Use --sample json|csv|all to import sample data")
                return
            
            self.import_offers(options)
        elif command == 'remove':
            self.remove_offers(options)
        elif command == 'list':
            self.list_offers(options)
        else:
            self.stdout.write(self.style.ERROR(f'Unknown command: {command}'))

    def import_offers(self, options):
        file_path = options['file_path']
        update_existing = options['update']
        clear = options['clear']
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise CommandError(f'File does not exist: {file_path}')
        
        # Clear existing offers if requested
        if clear:
            collection = Coupon.get_collection()
            if collection is not None:
                try:
                    result = collection.delete_many({})
                    self.stdout.write(self.style.SUCCESS(f'Deleted {result.deleted_count} existing offers'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error clearing offers: {str(e)}'))
            else:
                self.stdout.write(self.style.ERROR('Could not access offers collection'))
        
        # Import offers based on file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        offers_to_import = []
        
        if file_ext == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Handle both single offer and list of offers
                if isinstance(data, list):
                    offers_to_import = data
                else:
                    offers_to_import = [data]
                    
            except json.JSONDecodeError as e:
                raise CommandError(f'Invalid JSON format: {str(e)}')
            except Exception as e:
                raise CommandError(f'Error reading JSON file: {str(e)}')
                
        elif file_ext == '.csv':
            try:
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    csv_reader = csv.DictReader(csvfile)
                    for row in csv_reader:
                        offer = {}
                        for key, value in row.items():
                            if value:  # Skip empty values
                                # Handle type conversions
                                if key in ['usage_limit', 'usage_count']:
                                    try:
                                        offer[key] = int(value)
                                    except ValueError:
                                        offer[key] = 0
                                elif key == 'price' and value.replace('.', '', 1).isdigit():
                                    offer[key] = float(value)
                                elif key == 'category' and ',' in value:
                                    # Handle comma-separated categories
                                    offer[key] = [cat.strip() for cat in value.split(',')]
                                else:
                                    offer[key] = value
                        
                        if offer:
                            offers_to_import.append(offer)
            except Exception as e:
                raise CommandError(f'Error reading CSV file: {str(e)}')
        else:
            raise CommandError(f'Unsupported file type: {file_ext}. Please use JSON or CSV files.')
        
        # Import offers with validation
        total_count = len(offers_to_import)
        valid_count = 0
        invalid_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for offer in offers_to_import:
            # Validate offer
            is_valid, error = Coupon.validate_coupon(offer)
            
            if not is_valid:
                invalid_count += 1
                errors.append(f"Invalid offer {offer.get('coupon_code', 'unknown')}: {error}")
                continue
            
            # Check if offer already exists
            existing_offer = Coupon.get_by_code(offer['coupon_code'])
            
            if existing_offer:
                if update_existing:
                    # Update existing offer
                    Coupon.update_one({'coupon_code': offer['coupon_code']}, offer)
                    updated_count += 1
                    valid_count += 1
                else:
                    # Skip existing offer
                    skipped_count += 1
            else:
                # Insert new offer
                Coupon.insert_one(offer)
                valid_count += 1
        
        # Display results
        self.stdout.write(self.style.SUCCESS(f'Processed {total_count} offers:'))
        self.stdout.write(f'  Valid: {valid_count}')
        self.stdout.write(f'  Invalid: {invalid_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        
        if errors:
            self.stdout.write(self.style.WARNING('\nErrors:'))
            for error in errors[:10]:  # Show only first 10 errors to avoid flooding
                self.stdout.write(f'  - {error}')
            
            if len(errors) > 10:
                self.stdout.write(f'  ... and {len(errors) - 10} more errors')

    def remove_offers(self, options):
        code = options.get('code')
        remove_expired = options.get('expired')
        remove_all = options.get('all')
        
        collection = Coupon.get_collection()
        if collection is None:
            self.stdout.write(self.style.ERROR('Could not access offers collection'))
            return
            
        if code:
            # Remove specific offer by code
            result = collection.delete_one({'coupon_code': code})
            if result.deleted_count > 0:
                self.stdout.write(self.style.SUCCESS(f'Removed offer with code: {code}'))
            else:
                self.stdout.write(self.style.WARNING(f'No offer found with code: {code}'))
                
        elif remove_expired:
            # Remove all expired offers
            current_date = datetime.datetime.utcnow().isoformat()
            result = collection.delete_many({
                'valid_until': {'$lt': current_date}
            })
            self.stdout.write(self.style.SUCCESS(f'Removed {result.deleted_count} expired offers'))
            
        elif remove_all:
            # Remove all offers
            result = collection.delete_many({})
            self.stdout.write(self.style.SUCCESS(f'Removed all offers ({result.deleted_count} total)'))
            
        else:
            self.stdout.write(self.style.WARNING('No removal criteria specified. Use --code, --expired, or --all'))

    def list_offers(self, options):
        active_only = options.get('active')
        expired_only = options.get('expired')
        code_filter = options.get('code')
        min_amount = options.get('min_amount')
        max_amount = options.get('max_amount')
        discount_type = options.get('type')
        output_format = options.get('format', 'table')
        
        # Build query
        query = {}
        
        if active_only:
            current_date = datetime.datetime.utcnow().isoformat()
            query['$or'] = [
                {'valid_until': {'$exists': False}},
                {'valid_until': None},
                {'valid_until': {'$gt': current_date}}
            ]
            
        if expired_only:
            current_date = datetime.datetime.utcnow().isoformat()
            query['valid_until'] = {'$lt': current_date}
            
        if code_filter:
            # Use regex for partial matching
            query['coupon_code'] = {'$regex': f'.*{code_filter}.*', '$options': 'i'}
            
        if min_amount is not None:
            query['price'] = query.get('price', {})
            query['price']['$gte'] = min_amount
            
        if max_amount is not None:
            query['price'] = query.get('price', {})
            query['price']['$lte'] = max_amount
            
        if discount_type:
            query['price_type'] = discount_type
            
        # Get offers
        offers = Coupon.find(query)
        
        if not offers:
            self.stdout.write(self.style.WARNING('No offers found matching the criteria'))
            return
            
        # Display offers
        if output_format == 'json':
            # Convert ObjectIds to strings for JSON serialization
            for offer in offers:
                if '_id' in offer:
                    offer['_id'] = str(offer['_id'])
            self.stdout.write(json.dumps(offers, indent=2))
        else:
            # Table format
            self.stdout.write(f"Found {len(offers)} offers:")
            self.stdout.write("-" * 100)
            self.stdout.write(f"{'CODE':<15} | {'PRICE':<8} | {'TYPE':<12} | {'EXPIRES':<20} | {'TITLE':<30}")
            self.stdout.write("-" * 100)
            
            for offer in offers:
                expires = offer.get('valid_until', 'Never')
                if isinstance(expires, str) and len(expires) > 10:
                    # Truncate ISO format to just the date part
                    expires = expires.split('T')[0]
                    
                title = offer.get('title', '')
                if title and len(title) > 30:
                    title = title[:27] + '...'
                    
                self.stdout.write(
                    f"{offer.get('coupon_code', 'N/A'):<15} | "
                    f"{offer.get('price', 0):<8} | "
                    f"{offer.get('price_type', 'N/A'):<12} | "
                    f"{expires:<20} | "
                    f"{title:<30}"
                )
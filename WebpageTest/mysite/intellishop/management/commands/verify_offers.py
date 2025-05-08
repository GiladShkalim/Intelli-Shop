from django.core.management.base import BaseCommand
from intellishop.models.mongodb_models import Coupon
from intellishop.utils.mongodb_utils import get_collection_handle
import json
import datetime
import logging
from django.conf import settings
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Verify offers imported into MongoDB and display statistics'

    def add_arguments(self, parser):
        parser.add_argument('--codes', nargs='+', type=str, help='Specific coupon codes to verify')
        parser.add_argument('--source-files', nargs='+', type=str, help='Source files to check against')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table',
                           help='Output format (table or json)')
        parser.add_argument('--show-details', action='store_true', help='Show detailed information for each offer')
        parser.add_argument('--count-only', action='store_true', help='Show only count statistics')
        parser.add_argument('--sample-files', action='store_true', 
                           help='Verify against sample files in intellishop/data/coupons/')

    def handle(self, *args, **options):
        codes = options.get('codes')
        source_files = options.get('source_files', [])
        output_format = options.get('format', 'table')
        show_details = options.get('show_details', False)
        count_only = options.get('count_only', False)
        sample_files = options.get('sample_files', False)
        
        # Get the coupons collection
        collection = Coupon.get_collection()
        if collection is None:
            self.stdout.write(self.style.ERROR('Could not access coupons collection'))
            return
            
        # Build query
        query = {}
        if codes:
            query['coupon_code'] = {'$in': codes}
            
        # Get offers from database
        offers = list(collection.find(query))
        
        if not offers:
            self.stdout.write(self.style.WARNING('No offers found in the database that match your criteria'))
            return
            
        # Calculate statistics
        active_offers = 0
        expired_offers = 0
        free_shipping_offers = 0
        percent_offers = 0
        fixed_cart_offers = 0
        fixed_product_offers = 0
        bogo_offers = 0
        offer_by_codes = {}
        
        current_date = datetime.datetime.utcnow().isoformat()
        
        for offer in offers:
            # Check expiration status
            if 'valid_until' in offer and offer['valid_until']:
                if offer['valid_until'] < current_date:
                    expired_offers += 1
                else:
                    active_offers += 1
            else:
                active_offers += 1
                
            # Track by price type
            price_type = offer.get('price_type')
            if price_type == 'percentage':
                percent_offers += 1
            elif price_type == 'fixed_amount':
                fixed_cart_offers += 1
            elif price_type == 'buy_one_get_one':
                # New counter for new type
                bogo_offers = bogo_offers + 1 if 'bogo_offers' in locals() else 1

            # Track by code
            if offer.get('coupon_code'):
                offer_by_codes[offer['coupon_code']] = offer
        
        # Use sample files if requested
        if sample_files:
            base_dir = settings.BASE_DIR
            
            json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'coupon_samples.json')
            csv_path = os.path.join(base_dir, 'intellishop', 'data', 'coupons', 'sample_offers.csv')
            
            # Add sample files to source_files list if they exist
            if os.path.exists(json_path):
                source_files.append(json_path)
            if os.path.exists(csv_path):
                source_files.append(csv_path)
                
            if not source_files:
                self.stdout.write(self.style.WARNING('No sample files found in intellishop/data/coupons/'))
        
        # Check against source files if provided
        source_file_data = {}
        source_file_count = 0
        missing_from_db = []
        
        if source_files:
            for file_path in source_files:
                try:
                    if file_path.lower().endswith('.json'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            source_file_data[file_path] = data
                            source_file_count += len(data)
                            
                            # Check which codes are missing from DB
                            for item in data:
                                if 'coupon_code' in item and item['coupon_code'] not in offer_by_codes:
                                    missing_from_db.append({
                                        'code': item['coupon_code'],
                                        'source': file_path
                                    })
                        else:
                            if 'coupon_code' in data and data['coupon_code'] not in offer_by_codes:
                                missing_from_db.append({
                                    'code': data['coupon_code'],
                                    'source': file_path
                                })
                            source_file_data[file_path] = [data]
                            source_file_count += 1
                    elif file_path.lower().endswith('.csv'):
                        # For CSV, we just count the lines since we'd need to parse
                        # the CSV file which is more complex
                        with open(file_path, 'r', encoding='utf-8') as f:
                            # Skip header
                            next(f)
                            line_count = sum(1 for line in f)
                            source_file_data[file_path] = f"{line_count} CSV records"
                            source_file_count += line_count
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error reading source file {file_path}: {str(e)}"))
        
        # Output results based on format
        if output_format == 'json':
            result = {
                'total_offers': len(offers),
                'status': {
                    'active': active_offers,
                    'expired': expired_offers
                },
                'types': {
                    'percent': percent_offers,
                    'fixed_cart': fixed_cart_offers,
                    'fixed_product': fixed_product_offers,
                    'free_shipping': free_shipping_offers
                }
            }
            
            if source_files:
                result['source_files'] = {
                    'total_records': source_file_count,
                    'files': list(source_file_data.keys()),
                    'missing_from_db': missing_from_db
                }
                
            if show_details and not count_only:
                # Convert ObjectId to string for JSON serialization
                for offer in offers:
                    if '_id' in offer:
                        offer['_id'] = str(offer['_id'])
                result['offers'] = offers
                
            self.stdout.write(json.dumps(result, indent=2))
        else:
            # Table format
            self.stdout.write(self.style.SUCCESS(f"=== OFFER VERIFICATION RESULTS ==="))
            self.stdout.write(f"Total offers in database: {len(offers)}")
            self.stdout.write(f"Active offers: {active_offers}")
            self.stdout.write(f"Expired offers: {expired_offers}")
            self.stdout.write(f"Percent discount offers: {percent_offers}")
            self.stdout.write(f"Fixed cart offers: {fixed_cart_offers}")
            self.stdout.write(f"Fixed product offers: {fixed_product_offers}")
            self.stdout.write(f"Free shipping offers: {free_shipping_offers}")
            
            if source_files:
                self.stdout.write("\n=== SOURCE FILE VERIFICATION ===")
                self.stdout.write(f"Total records in source files: {source_file_count}")
                
                for file_path, data in source_file_data.items():
                    self.stdout.write(f"File: {file_path}")
                    if isinstance(data, str):
                        self.stdout.write(f"  - {data}")
                    else:
                        self.stdout.write(f"  - {len(data)} JSON records")
                
                if missing_from_db:
                    self.stdout.write("\nMissing from database:")
                    for item in missing_from_db:
                        self.stdout.write(f"  - Code '{item['code']}' from {item['source']}")
                else:
                    self.stdout.write("\nAll source file records found in database!")
            
            if show_details and not count_only:
                self.stdout.write("\n=== OFFER DETAILS ===")
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
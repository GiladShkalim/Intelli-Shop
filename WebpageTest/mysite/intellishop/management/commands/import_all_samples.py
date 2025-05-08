from django.core.management.base import BaseCommand
from intellishop.utils.initialize_db import import_sample_coupon_data
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import all sample data from the app data directories'

    def add_arguments(self, parser):
        parser.add_argument('--skip-coupons', action='store_true', help='Skip importing coupon data')
        parser.add_argument('--migrate-coupons', action='store_true', help='Migrate existing coupons to new schema')

    def handle(self, *args, **options):
        skip_coupons = options.get('skip_coupons', False)
        migrate_coupons = options.get('migrate_coupons', False)
        
        self.stdout.write(self.style.SUCCESS('Starting sample data import...'))
        
        # Import coupon data
        if not skip_coupons:
            self.stdout.write('Importing coupon data...')
            import_sample_coupon_data()
            self.stdout.write(self.style.SUCCESS('Coupon data import completed'))
        
        # Migrate existing coupons if requested
        if migrate_coupons:
            self.stdout.write('Migrating existing coupons to new schema...')
            try:
                # Import the command and run it programmatically
                from intellishop.management.commands.migrate_coupons import Command as MigrateCouponsCommand
                cmd = MigrateCouponsCommand()
                # Create a custom namespace with the options
                from argparse import Namespace
                options = Namespace(dry_run=False)
                # Run the command
                cmd.handle(options=options)
                self.stdout.write(self.style.SUCCESS('Coupon migration completed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error during coupon migration: {str(e)}'))
        
        # Future: Add more data import functions here
        # import_sample_product_data()
        # import_sample_user_data()
        
        self.stdout.write(self.style.SUCCESS('All sample data imports completed successfully'))
from django.core.management.base import BaseCommand
from intellishop.utils.mongodb_utils import get_db_handle
from django.test import TestCase
from intellishop.models.mongodb_models import Coupon
import datetime
import json
import os
from django.conf import settings

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

class CouponModelTestCase(TestCase):
    def setUp(self):
        # Create test database connection
        self.collection = Coupon.get_collection()
        # Clear any existing test data
        if self.collection:
            self.collection.delete_many({})
            
    def tearDown(self):
        # Clean up after tests
        if self.collection:
            self.collection.delete_many({})
    
    def test_coupon_validation(self):
        """Test that coupon validation works correctly"""
        # Valid coupon
        valid_coupon = {
            "title": "Test Coupon",
            "price": 25,
            "price_type": "percentage",
            "description": "Test description",
            "discount_link": "https://example.com/test",
            "coupon_code": "TEST25",
            "valid_until": datetime.datetime.now().isoformat()
        }
        
        is_valid, error = Coupon.validate_coupon(valid_coupon)
        self.assertTrue(is_valid, f"Valid coupon failed validation: {error}")
        
        # Missing required fields
        invalid_coupon = {
            "title": "Test Coupon",
            "price": 25,
            # Missing discount_link
            "coupon_code": "TEST25",
        }
        
        is_valid, error = Coupon.validate_coupon(invalid_coupon)
        self.assertFalse(is_valid, "Invalid coupon passed validation")
        
        # Test auto-inferred price_type
        auto_type_coupon = {
            "title": "Auto Type Coupon",
            "price": "25%",
            "description": "Should infer percentage type",
            "discount_link": "https://example.com/test",
            "coupon_code": "AUTO25",
            "valid_until": datetime.datetime.now().isoformat()
        }
        
        is_valid, error = Coupon.validate_coupon(auto_type_coupon)
        self.assertTrue(is_valid, f"Auto-type coupon failed validation: {error}")
        self.assertEqual(auto_type_coupon["price_type"], "percentage")
        
    def test_get_by_code(self):
        """Test retrieving a coupon by code"""
        # Insert a test coupon
        test_coupon = {
            "title": "Get By Code Test",
            "price": 50,
            "price_type": "percentage",
            "description": "Test retrieval by code",
            "discount_link": "https://example.com/code-test",
            "coupon_code": "GETTEST",
            "valid_until": datetime.datetime.now().isoformat()
        }
        
        if self.collection:
            self.collection.insert_one(test_coupon)
            
            # Retrieve by code
            retrieved = Coupon.get_by_code("GETTEST")
            self.assertIsNotNone(retrieved, "Failed to retrieve coupon by code")
            self.assertEqual(retrieved["coupon_code"], "GETTEST")
            
            # Try to retrieve non-existent coupon
            non_existent = Coupon.get_by_code("NONEXISTENT")
            self.assertIsNone(non_existent, "Retrieved a non-existent coupon")
    
    def test_csv_import(self):
        """Test importing coupons from CSV"""
        # Create a temporary CSV file
        import tempfile
        import csv
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as temp_csv:
            # Write header and data
            writer = csv.writer(temp_csv)
            writer.writerow(['title', 'price', 'price_type', 'description', 'discount_link', 
                             'terms_and_conditions', 'coupon_code', 'valid_until'])
            writer.writerow(['CSV Test Coupon', '30', 'percentage', 'CSV import test', 
                             'https://example.com/csv-test', 'Test terms', 'CSVTEST', 
                             datetime.datetime.now().isoformat()])
            
            csv_path = temp_csv.name
            
        try:
            # Import the CSV
            results = Coupon.import_from_csv(csv_path)
            
            # Check results
            self.assertEqual(results['total'], 1, "Wrong total count in import results")
            self.assertEqual(results['valid'], 1, "Wrong valid count in import results")
            self.assertEqual(results['invalid'], 0, "Should have no invalid entries")
            
            # Verify the coupon was imported
            imported = Coupon.get_by_code("CSVTEST")
            self.assertIsNotNone(imported, "Failed to import coupon from CSV")
            self.assertEqual(imported["title"], "CSV Test Coupon")
            
        finally:
            # Clean up
            os.unlink(csv_path)
            
    def test_legacy_mapping(self):
        """Test mapping of legacy fields to new schema"""
        # Create a legacy coupon object
        legacy_coupon = {
            "code": "LEGACY",
            "amount": 15,
            "discount_type": "percent",
            "description": "Legacy coupon",
            "date_expires": datetime.datetime.now().isoformat(),
            "individual_use": True,
            "usage_limit": 5,
            "free_shipping": True,
            "exclude_sale_items": True,
            "minimum_amount": 100,
            "maximum_amount": 500,
            "product_categories": "electronics,summer"
        }
        
        # Map to new schema
        mapped = Coupon._map_legacy_fields(legacy_coupon)
        
        # Verify mapping
        self.assertEqual(mapped["coupon_code"], "LEGACY")
        self.assertEqual(mapped["price"], 15)
        self.assertEqual(mapped["price_type"], "percentage")
        self.assertEqual(mapped["valid_until"], legacy_coupon["date_expires"])
        self.assertEqual(mapped["usage_limit"], 5)
        
        # Check terms and conditions
        self.assertIn("Minimum purchase amount: 100", mapped["terms_and_conditions"])
        self.assertIn("Maximum purchase amount: 500", mapped["terms_and_conditions"])
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from shop.models import Product
from shop.tests.utils import make_product


class SeedProductsCommandTests(TestCase):
    def call(self):
        out = StringIO()
        call_command('seed_products', stdout=out)
        return out.getvalue()

    def test_loads_fixture_into_empty_database(self):
        output = self.call()
        self.assertEqual(Product.objects.count(), 8)
        self.assertIn('Загружено товаров: 8', output)

    def test_skips_when_products_exist(self):
        product = make_product(quantity=3)
        output = self.call()
        self.assertEqual(Product.objects.count(), 1)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 3)
        self.assertIn('загрузка пропущена', output)

    def test_running_twice_does_not_reset_stock(self):
        self.call()
        Product.objects.first().sell(9)
        self.call()
        self.assertEqual(Product.objects.first().quantity, 1)

    def test_fixture_products_are_consistent(self):
        self.call()
        for product in Product.objects.all():
            with self.subTest(product=product.name):
                self.assertEqual(product.quantity, product.initial_quantity)
                self.assertFalse(product.price_increased)
                self.assertGreater(product.price, 0)

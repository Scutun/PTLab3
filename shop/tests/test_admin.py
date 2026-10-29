from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from shop.admin import ProductAdmin, PurchaseAdmin
from shop.models import Product, Purchase
from shop.tests.utils import make_product, make_purchase


class AdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@a.ru', 'pass')
        self.client.force_login(self.user)
        self.product = make_product()
        make_purchase(self.product)

    def test_models_registered(self):
        self.assertIsInstance(admin.site._registry[Product], ProductAdmin)
        self.assertIsInstance(admin.site._registry[Purchase], PurchaseAdmin)

    def test_list_display(self):
        self.assertIn('quantity', ProductAdmin.list_display)
        self.assertIn('price_increased', ProductAdmin.list_display)
        self.assertIn('count', PurchaseAdmin.list_display)

    def test_product_changelist(self):
        response = self.client.get(reverse('admin:shop_product_changelist'))
        self.assertContains(response, 'Лопата')

    def test_purchase_changelist(self):
        response = self.client.get(reverse('admin:shop_purchase_changelist'))
        self.assertContains(response, 'Иванов')

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('admin:shop_product_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

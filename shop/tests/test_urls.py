from django.test import SimpleTestCase
from django.urls import resolve, reverse

from shop import views


class UrlTests(SimpleTestCase):
    def test_index_url(self):
        self.assertEqual(reverse('index'), '/')
        self.assertEqual(resolve('/').func, views.index)

    def test_buy_url(self):
        self.assertEqual(reverse('buy', args=[5]), '/buy/5/')
        match = resolve('/buy/5/')
        self.assertEqual(match.func.view_class, views.PurchaseCreate)
        self.assertEqual(match.kwargs, {'product_id': 5})

    def test_admin_url(self):
        self.assertEqual(reverse('admin:index'), '/admin/')

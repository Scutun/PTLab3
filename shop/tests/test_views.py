from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from shop.forms import PurchaseForm
from shop.models import Product, Purchase
from shop.tests.utils import PURCHASE_DATA, make_product


class PurchaseCreateTestCase(TestCase):
    """Исходный тест учебного проекта."""

    def setUp(self):
        self.client = Client()

    def test_webpage_accessibility(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)


class IndexViewTests(TestCase):
    def setUp(self):
        self.shovel = make_product(name='Лопата', price=1200,
                                   initial_quantity=10, quantity=7)
        self.can = make_product(name='Лейка', price=660, initial_quantity=3,
                                quantity=0, price_increased=True)

    def test_uses_template(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/index.html')
        self.assertTemplateUsed(response, 'shop/base.html')

    def test_context_contains_all_products(self):
        response = self.client.get(reverse('index'))
        self.assertQuerySetEqual(response.context['products'],
                                 [self.shovel, self.can])

    def test_shows_price_and_stock(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'Лопата')
        self.assertContains(response, '1200')
        self.assertContains(response, '7 из 10')

    def test_buy_link_only_for_available_products(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, reverse('buy', args=[self.shovel.pk]))
        self.assertNotContains(response, reverse('buy', args=[self.can.pk]))
        self.assertContains(response, 'нет в наличии', count=1)

    def test_increased_price_badge(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'цена +20 %', count=1)

    def test_empty_shop(self):
        Product.objects.all().delete()
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'Товаров пока нет.')


class PurchaseGetTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.url = reverse('buy', args=[self.product.pk])

    def test_page_with_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/purchase_form.html')
        self.assertEqual(response.context['product'], self.product)
        self.assertIsInstance(response.context['form'], PurchaseForm)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_form_is_bound_to_product(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['form'].product, self.product)

    def test_nonexistent_product_get_returns_404(self):
        response = self.client.get(reverse('buy', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_product_post_returns_404(self):
        response = self.client.post(reverse('buy', args=[9999]),
                                    PURCHASE_DATA)
        self.assertEqual(response.status_code, 404)

    def test_sold_out_product_page_has_no_form(self):
        Product.objects.filter(pk=self.product.pk).update(quantity=0)
        response = self.client.get(self.url)
        self.assertContains(response, 'Товар закончился, покупка невозможна.')
        self.assertNotContains(response, '<form')


class PurchasePostTests(TestCase):
    def setUp(self):
        self.product = make_product(price=1200, initial_quantity=10)
        self.url = reverse('buy', args=[self.product.pk])

    def post(self, **data):
        return self.client.post(self.url, {**PURCHASE_DATA, **data})

    def test_creates_purchase(self):
        self.post(person='Петров', address='Лесная ул., 5', count=2)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.product, self.product)
        self.assertEqual(purchase.person, 'Петров')
        self.assertEqual(purchase.address, 'Лесная ул., 5')
        self.assertEqual(purchase.count, 2)
        self.assertEqual(purchase.price, 1200)

    def test_decreases_stock(self):
        self.post(count=3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 7)

    def test_done_page(self):
        response = self.post(count=3)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/purchase_done.html')
        self.assertContains(response, 'Спасибо за покупку, Иванов!')
        self.assertContains(response, 'Итого к оплате: <b>3600 руб.</b>',
                            html=False)
        self.assertContains(response, 'Осталось на складе: 7 шт.')
        self.assertFalse(response.context['price_changed'])
        self.assertNotContains(response, 'новая цена')

    def test_buyer_pays_old_price_when_price_increases(self):
        response = self.post(count=6)
        self.assertTrue(response.context['price_changed'])
        self.assertContains(response, 'новая цена 1440 руб.')
        self.assertEqual(Purchase.objects.get().price, 1200)

    def test_next_buyer_pays_new_price(self):
        self.post(count=6)
        response = self.post(count=2)
        self.assertEqual(Purchase.objects.latest('id').price, 1440)
        self.assertContains(response, '2880 руб.')
        self.assertFalse(response.context['price_changed'])

    def test_cannot_buy_more_than_in_stock(self):
        response = self.post(count=11)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/purchase_form.html')
        self.assertFormError(response.context['form'], 'count',
                             'На складе только 10 шт.')
        self.assertEqual(Purchase.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

    def test_cannot_buy_sold_out_product(self):
        Product.objects.filter(pk=self.product.pk).update(quantity=0)
        response = self.post()
        self.assertContains(response, 'Товар закончился')
        self.assertEqual(Purchase.objects.count(), 0)

    def test_invalid_form_does_not_create_purchase(self):
        response = self.client.post(self.url, {'person': '', 'address': '',
                                               'count': 0})
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(set(form.errors), {'person', 'address', 'count'})
        self.assertEqual(Purchase.objects.count(), 0)

    def test_buying_whole_stock_hides_buy_button(self):
        self.post(count=10)
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'нет в наличии')
        self.assertContains(response, '0 из 10')

    def test_product_row_is_locked(self):
        with CaptureQueriesContext(connection) as queries:
            self.post()
        self.assertTrue(any('FOR UPDATE' in q['sql']
                            for q in queries.captured_queries))

    def test_csrf_token_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, PURCHASE_DATA)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Purchase.objects.count(), 0)

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from shop.models import OutOfStockError, Product, Purchase
from shop.tests.utils import make_product, make_purchase


class ProductTestCase(TestCase):
    """Исходные тесты учебного проекта."""

    def setUp(self):
        Product.objects.create(name="book", price="740")
        Product.objects.create(name="pencil", price="50")

    def test_correctness_types(self):
        self.assertIsInstance(Product.objects.get(name="book").name, str)
        self.assertIsInstance(Product.objects.get(name="book").price, int)
        self.assertIsInstance(Product.objects.get(name="pencil").name, str)
        self.assertIsInstance(Product.objects.get(name="pencil").price, int)

    def test_correctness_data(self):
        self.assertEqual(Product.objects.get(name="book").price, 740)
        self.assertEqual(Product.objects.get(name="pencil").price, 50)


class ProductModelTests(TestCase):
    def setUp(self):
        self.product = make_product()

    def test_str_returns_name(self):
        self.assertEqual(str(self.product), 'Лопата')

    def test_field_types(self):
        product = Product.objects.get(pk=self.product.pk)
        self.assertIsInstance(product.quantity, int)
        self.assertIsInstance(product.initial_quantity, int)
        self.assertIsInstance(product.price_increased, bool)

    def test_default_values(self):
        product = Product.objects.create(name='Грабли', price=650)
        self.assertEqual(product.initial_quantity, 10)
        self.assertEqual(product.quantity, 10)
        self.assertFalse(product.price_increased)

    def test_verbose_names(self):
        self.assertEqual(Product._meta.verbose_name, 'товар')
        self.assertEqual(Product._meta.verbose_name_plural, 'товары')
        self.assertEqual(Product._meta.get_field('quantity').verbose_name,
                         'количество на складе')

    def test_ordering_by_id(self):
        second = make_product(name='Грабли')
        self.assertEqual(list(Product.objects.all()),
                         [self.product, second])

    def test_is_available(self):
        self.assertTrue(self.product.is_available)
        self.assertFalse(make_product(name='Лейка', quantity=0).is_available)

    def test_is_stock_halved_boundaries(self):
        cases = [
            # (начальное, текущее, ожидаемый результат)
            (10, 10, False), (10, 6, False), (10, 5, False),
            (10, 4, True), (10, 0, True),
            (5, 3, False), (5, 2, True),
            (1, 1, False), (1, 0, True), (0, 0, False),
        ]
        for initial, quantity, expected in cases:
            with self.subTest(initial=initial, quantity=quantity):
                product = Product(name='x', price=1,
                                  initial_quantity=initial, quantity=quantity)
                self.assertIs(product.is_stock_halved(), expected)

    def test_increased_price(self):
        cases = [(1000, 1200), (999, 1199), (1200, 1440), (450, 540),
                 (1, 1), (3, 4), (0, 0)]
        for price, expected in cases:
            with self.subTest(price=price):
                self.assertEqual(Product.increased_price(price), expected)

    def test_price_increase_percent_constant(self):
        self.assertEqual(Product.PRICE_INCREASE_PERCENT, 20)


class ProductSellTests(TestCase):
    def setUp(self):
        self.product = make_product(price=1200, initial_quantity=10)

    def refreshed(self):
        self.product.refresh_from_db()
        return self.product

    def test_sell_decreases_quantity_and_saves(self):
        self.product.sell(3)
        self.assertEqual(self.refreshed().quantity, 7)

    def test_sell_default_count_is_one(self):
        self.product.sell()
        self.assertEqual(self.refreshed().quantity, 9)

    def test_sell_whole_stock(self):
        self.product.sell(10)
        product = self.refreshed()
        self.assertEqual(product.quantity, 0)
        self.assertFalse(product.is_available)

    def test_sell_more_than_stock_raises_and_keeps_data(self):
        with self.assertRaises(OutOfStockError):
            self.product.sell(11)
        product = self.refreshed()
        self.assertEqual(product.quantity, 10)
        self.assertEqual(product.price, 1200)

    def test_out_of_stock_error_message(self):
        with self.assertRaisesMessage(OutOfStockError,
                                      'На складе только 10 шт. товара «Лопата»'):
            self.product.sell(20)

    def test_sell_from_empty_stock_raises(self):
        empty = make_product(name='Лейка', quantity=0)
        with self.assertRaises(OutOfStockError):
            empty.sell(1)

    def test_sell_non_positive_count_raises(self):
        for count in (0, -1, -10):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    self.product.sell(count)
        self.assertEqual(self.refreshed().quantity, 10)

    def test_price_unchanged_at_exactly_half(self):
        self.product.sell(5)
        product = self.refreshed()
        self.assertEqual(product.price, 1200)
        self.assertFalse(product.price_increased)

    def test_price_increased_below_half(self):
        self.product.sell(6)
        product = self.refreshed()
        self.assertEqual(product.price, 1440)
        self.assertTrue(product.price_increased)

    def test_price_increased_only_once(self):
        self.product.sell(6)
        self.product.sell(3)
        self.product.sell(1)
        product = self.refreshed()
        self.assertEqual(product.quantity, 0)
        self.assertEqual(product.price, 1440)

    def test_price_increase_when_selling_one_by_one(self):
        prices = []
        for _ in range(10):
            self.product.sell(1)
            prices.append(self.refreshed().price)
        self.assertEqual(prices, [1200] * 5 + [1440] * 5)

    def test_price_increase_on_last_unit(self):
        single = make_product(name='Тачка', price=4800, initial_quantity=1)
        single.sell(1)
        single.refresh_from_db()
        self.assertEqual(single.price, 5760)

    def test_already_increased_price_not_increased_again(self):
        product = make_product(name='Шланг', price=2760, initial_quantity=10,
                               quantity=3, price_increased=True)
        product.sell(1)
        product.refresh_from_db()
        self.assertEqual(product.price, 2760)

    def test_sell_saves_only_stock_fields(self):
        self.product.name = 'Несохранённое имя'
        self.product.sell(1)
        self.assertEqual(self.refreshed().name, 'Лопата')


class ProductConstraintTests(TestCase):
    def test_quantity_cannot_exceed_initial_quantity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_product(initial_quantity=10, quantity=11)

    def test_price_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_product(price=-1)

    def test_quantity_cannot_be_negative(self):
        product = make_product()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(quantity=-1)


class PurchaseTestCase(TestCase):
    """Исходные тесты учебного проекта."""

    def setUp(self):
        self.product_book = Product.objects.create(name="book", price="740")
        self.datetime = datetime.now()
        Purchase.objects.create(product=self.product_book,
                                person="Ivanov",
                                address="Svetlaya St.")

    def test_correctness_types(self):
        purchase = Purchase.objects.get(product=self.product_book)
        self.assertIsInstance(purchase.person, str)
        self.assertIsInstance(purchase.address, str)
        self.assertIsInstance(purchase.date, datetime)

    def test_correctness_data(self):
        purchase = Purchase.objects.get(product=self.product_book)
        self.assertEqual(purchase.person, "Ivanov")
        self.assertEqual(purchase.address, "Svetlaya St.")
        self.assertLess(abs(purchase.date - self.datetime),
                        timedelta(seconds=5))


class PurchaseModelTests(TestCase):
    def setUp(self):
        self.product = make_product()

    def test_str(self):
        purchase = make_purchase(self.product, count=2)
        self.assertEqual(str(purchase), 'Иванов: Лопата × 2')

    def test_total(self):
        purchase = Purchase(product=self.product, person='Петров',
                            address='Лесная ул.', count=3, price=740)
        self.assertEqual(purchase.total, 2220)

    def test_default_values(self):
        purchase = Purchase.objects.create(product=self.product,
                                           person='Петров', address='Лесная')
        self.assertEqual(purchase.count, 1)
        self.assertEqual(purchase.price, 0)
        self.assertEqual(purchase.total, 0)

    def test_date_is_set_automatically(self):
        before = datetime.now()
        purchase = make_purchase(self.product)
        self.assertIsNotNone(purchase.date)
        self.assertGreaterEqual(purchase.date, before)

    def test_ordering_newest_first(self):
        first = make_purchase(self.product, person='Первый')
        second = make_purchase(self.product, person='Второй')
        Purchase.objects.filter(pk=first.pk).update(
            date=datetime.now() - timedelta(days=1))
        self.assertEqual(list(Purchase.objects.all()), [second, first])

    def test_purchases_deleted_with_product(self):
        make_purchase(self.product)
        make_purchase(self.product)
        self.product.delete()
        self.assertEqual(Purchase.objects.count(), 0)

    def test_reverse_relation(self):
        purchase = make_purchase(self.product)
        self.assertEqual(list(self.product.purchase_set.all()), [purchase])

    def test_count_must_be_positive(self):
        purchase = Purchase(product=self.product, person='Петров',
                            address='Лесная', count=0, price=10)
        with self.assertRaises(ValidationError) as ctx:
            purchase.full_clean()
        self.assertIn('count', ctx.exception.message_dict)

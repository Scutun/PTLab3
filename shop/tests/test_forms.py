from django.test import TestCase

from shop.forms import PurchaseForm
from shop.tests.utils import PURCHASE_DATA, make_product


class PurchaseFormTests(TestCase):
    def setUp(self):
        self.product = make_product(initial_quantity=10, quantity=4)

    def form(self, product='default', **data):
        if product == 'default':
            product = self.product
        return PurchaseForm(data={**PURCHASE_DATA, **data}, product=product)

    def test_valid_form(self):
        form = self.form(count=2)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['count'], 2)

    def test_fields(self):
        self.assertEqual(list(PurchaseForm().fields),
                         ['person', 'address', 'count'])

    def test_labels(self):
        fields = PurchaseForm().fields
        self.assertEqual(fields['person'].label, 'Ваше имя')
        self.assertEqual(fields['address'].label, 'Адрес доставки')
        self.assertEqual(fields['count'].label, 'Количество, шт.')

    def test_required_fields(self):
        form = PurchaseForm(data={}, product=self.product)
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {'person', 'address', 'count'})

    def test_invalid_counts(self):
        for count in (0, -1, 'abc', '1.5'):
            with self.subTest(count=count):
                form = self.form(count=count)
                self.assertFalse(form.is_valid())
                self.assertIn('count', form.errors)

    def test_count_equal_to_stock_is_valid(self):
        self.assertTrue(self.form(count=4).is_valid())

    def test_count_more_than_stock_is_invalid(self):
        form = self.form(count=5)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['count'], ['На складе только 4 шт.'])

    def test_without_product_stock_is_not_checked(self):
        form = self.form(product=None, count=1000)
        self.assertTrue(form.is_valid())

    def test_count_widget_limits(self):
        attrs = self.form().fields['count'].widget.attrs
        self.assertEqual(attrs['min'], 1)
        self.assertEqual(attrs['max'], 4)

    def test_person_max_length(self):
        self.assertFalse(self.form(person='я' * 201).is_valid())
        self.assertTrue(self.form(person='я' * 200).is_valid())

    def test_save_without_commit_does_not_touch_db(self):
        form = self.form()
        self.assertTrue(form.is_valid())
        purchase = form.save(commit=False)
        self.assertIsNone(purchase.pk)

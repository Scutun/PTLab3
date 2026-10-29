"""Вспомогательные функции для создания тестовых объектов."""
from shop.models import Product, Purchase


def make_product(name='Лопата', price=1200, initial_quantity=10,
                 quantity=None, **kwargs):
    if quantity is None:
        quantity = initial_quantity
    return Product.objects.create(name=name, price=price,
                                  initial_quantity=initial_quantity,
                                  quantity=quantity, **kwargs)


def make_purchase(product, person='Иванов', address='Садовая ул., 1',
                  count=1, price=None):
    return Purchase.objects.create(
        product=product, person=person, address=address, count=count,
        price=product.price if price is None else price)


PURCHASE_DATA = {'person': 'Иванов', 'address': 'Садовая ул., 1',
                 'count': 1}

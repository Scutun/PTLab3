import importlib
import os
from unittest import mock

from django.test import SimpleTestCase

import tplab2.settings


class SettingsTests(SimpleTestCase):
    """Настройки зависят от переменных окружения. Модуль settings
    перезагружается с подменёнными переменными (unittest.mock)."""

    def load(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return importlib.reload(tplab2.settings)

    def tearDown(self):
        importlib.reload(tplab2.settings)

    def test_local_defaults(self):
        settings = self.load()
        self.assertTrue(settings.DEBUG)
        self.assertNotIn('SECURE_PROXY_SSL_HEADER', vars(settings))
        db = settings.DATABASES['default']
        self.assertEqual(db['NAME'], 'django_db')
        self.assertEqual(db['HOST'], 'localhost')

    def test_database_password_from_environment(self):
        settings = self.load(DATABASE_PASSWORD='ps_password')
        self.assertEqual(settings.DATABASES['default']['PASSWORD'],
                         'ps_password')

    def test_render_environment(self):
        settings = self.load(RENDER='true', SECRET_KEY='secret',
                             RENDER_EXTERNAL_HOSTNAME='shop.onrender.com')
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.SECRET_KEY, 'secret')
        self.assertIn('shop.onrender.com', settings.ALLOWED_HOSTS)
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS,
                         ['https://shop.onrender.com'])
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER,
                         ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_debug_can_be_overridden(self):
        self.assertFalse(self.load(DJANGO_DEBUG='False').DEBUG)
        self.assertTrue(self.load(RENDER='true', DJANGO_DEBUG='True').DEBUG)

    def test_database_url(self):
        settings = self.load(
            DATABASE_URL='postgres://user:pw@db.example.com:5433/shop'
                         '?sslmode=require')
        db = settings.DATABASES['default']
        self.assertEqual((db['USER'], db['PASSWORD'], db['HOST'], db['PORT'],
                          db['NAME']),
                         ('user', 'pw', 'db.example.com', 5433, 'shop'))
        self.assertEqual(db['OPTIONS'], {'sslmode': 'require'})
        self.assertTrue(db['CONN_HEALTH_CHECKS'])

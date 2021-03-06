# coding=utf8
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from module.plugins.hoster.MegaCoNz import MegaCrypto
from tests.unit.base import BaseUnitTestCase


class TestMegaCrypto(BaseUnitTestCase):

    def test_base64_decode(self):
        value_to_expected_tuples = (
            (b'', b''),
            (u'', b''),
            (b'test', b'\xb5\xeb-'),
            (u'test', b'\xb5\xeb-'),
            (b'test_1', b'\xb5\xeb-\xff'),
            (u'test_1', b'\xb5\xeb-\xff'),
            (b'test-2', b'\xb5\xeb-\xfb'),
            (u'test-2', b'\xb5\xeb-\xfb'),
        )

        for value, expected in value_to_expected_tuples:
            self.assertEqual(expected, MegaCrypto.base64_decode(value))

    def test_base64_encode(self):
        value_to_expected_tuples = (
            (b'', b''),
            (u'', b''),
            (b'test', b'dGVzdA=='),
            (u'test', b'dGVzdA=='),
            (b'test_1', b'dGVzdF8x'),
            (u'test_1', b'dGVzdF8x'),
            (b'test-2', b'dGVzdC0y'),
            (u'test-2', b'dGVzdC0y'),
        )

        for value, expected in value_to_expected_tuples:
            self.assertEqual(expected, MegaCrypto.base64_encode(value))

    def test_str_to_a32(self):
        value_to_expected_tuples = (
            (b'', ()),
            (u'', ()),
            (b'test', (1952805748,)),
            (u'test', (1952805748,)),
            (b'test_1', (1952805748, 1597046784)),
            (u'test_1', (1952805748, 1597046784)),
            (b'test-2', (1952805748, 758251520)),
            (u'test-2', (1952805748, 758251520)),
        )

        for value, expected in value_to_expected_tuples:
            self.assertEqual(expected, MegaCrypto.str_to_a32(value))

    def test_cbc_encrypt_and_decrypt(self):
        key = (1952805748, 1597046784, 1597046784, 1597046784)
        encrypted_to_decrypted_tuples = (
            (
                b'\xfa\xb9\xcf\xc2lcT\xa2\xdf-\xe0\xe0\\[\xfeK\xb1\x98\x19\nZ\xd3\xbe\xfa\t\xfb\xb9\x02\xd3\xbd\x8b\xb5',
                b'\x16<\xccQ\xa7\xad[\rF\x03\x0e\xd8j\xe0\xee\x89\x9eL\xccH\xa5\x0e\x82\xa7\x9f\xb6\xe0\x05\x9dAy\xb8',
            ),
        )

        for encrypted, decrypted in encrypted_to_decrypted_tuples:
            self.assertEqual(decrypted, MegaCrypto.cbc_decrypt(encrypted, key))
            self.assertEqual(encrypted, MegaCrypto.cbc_encrypt(decrypted, key))

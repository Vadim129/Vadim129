"""Small offline tests for the private audio transport; no network or model."""
import unittest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from ai_artifacts import seal,unseal


class TransferTests(unittest.TestCase):
    def keys(self):
        key=X25519PrivateKey.generate()
        private=key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        return private,public

    def test_roundtrip(self):
        private,public=self.keys()
        for data in (b'',b'audio-test',bytes(range(256))*100):
            with self.subTest(length=len(data)):
                self.assertEqual(unseal(seal(data,public),private),data)

    def test_tamper_rejected(self):
        private,public=self.keys()
        blob=bytearray(seal(b'audio-test',public));blob[-1]^=1
        with self.assertRaises(InvalidTag):
            unseal(bytes(blob),private)

    def test_wrong_worker_rejected(self):
        _,public=self.keys();other,_=self.keys()
        with self.assertRaises(InvalidTag):
            unseal(seal(b'audio-test',public),other)

    def test_bad_header_rejected(self):
        private,_=self.keys()
        with self.assertRaises(ValueError):
            unseal(b'not-an-encrypted-audio-file',private)


if __name__=='__main__':
    unittest.main()

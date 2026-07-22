import unittest

from ping.hasher import canonical_json, content_hash


class HasherTests(unittest.TestCase):
    def test_canonical_json_ignores_key_order_and_extra_whitespace(self) -> None:
        left = {"title": " Senior   Engineer ", "company": "Acme", "empty": "   "}
        right = {"company": "Acme", "title": "Senior Engineer"}

        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(content_hash(left), content_hash(right))


if __name__ == "__main__":
    unittest.main()

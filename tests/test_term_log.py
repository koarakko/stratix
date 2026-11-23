import unittest
from dataclasses import replace
from services.replication.term_log import append_term, verify_term_log, TermLogError, GENESIS

class TermLogTests(unittest.TestCase):
    def setUp(self):
        self.log = append_term(append_term((), 1, b'place'), 2, b'fill')

    def test_round_trip(self):
        self.assertEqual(verify_term_log(self.log), self.log[-1].entry_hash)
        self.assertEqual(self.log, append_term(append_term((), 1, b'place'), 2, b'fill'))

    def test_empty(self):
        self.assertEqual(verify_term_log(()), GENESIS)

    def test_term_tampering(self):
        with self.assertRaises(TermLogError):
            verify_term_log((replace(self.log[0], term=2), self.log[1]))

    def test_payload_tampering(self):
        with self.assertRaises(TermLogError):
            verify_term_log((replace(self.log[0], payload=b'cancel'), self.log[1]))

    def test_order_and_link(self):
        for log in (self.log[::-1], (self.log[1],), (self.log[0], self.log[0]),
                    (self.log[0], replace(self.log[1], previous_hash=GENESIS))):
            with self.subTest(log=log), self.assertRaises(TermLogError):
                verify_term_log(log)

    def test_decreasing_term(self):
        with self.assertRaises(TermLogError):
            append_term(self.log, 1, b'late')

    def test_bad_term_types(self):
        for term in (True, 1.0, 0, -1, 2**64):
            with self.subTest(term=term), self.assertRaises(TermLogError):
                append_term((), term, b'x')

    def test_bad_payload(self):
        for payload in ('text', bytearray(b'x'), None):
            with self.subTest(payload=payload), self.assertRaises(TermLogError):
                append_term((), 1, payload)

    def test_hash_domain_separation(self):
        from services.replication.log_integrity import append
        self.assertNotEqual(self.log[0].entry_hash, append((), b'place')[0].entry_hash)

    def test_immutable_input(self):
        original = self.log
        extended = append_term(original, 2, b'new')
        self.assertEqual(len(original), 2)
        self.assertEqual(len(extended), 3)

    def test_invalid_sequence_type(self):
        with self.assertRaises(TermLogError):
            verify_term_log((replace(self.log[0], sequence=True),))

    def test_term_monotonicity(self):
        with self.assertRaises(TermLogError):
            verify_term_log((self.log[0], replace(self.log[1], term=0)))

if __name__ == '__main__':
    unittest.main()

import unittest
from dataclasses import replace
from services.replication.log_integrity import (
    GENESIS, LogEntry, LogIntegrityError, append, verify,
)


class LogIntegrityTests(unittest.TestCase):
    def test_append_verify_and_deterministic_replay(self):
        original = append((), b"place:1")
        history = append(original, b"cancel:1")
        self.assertEqual(len(original), 1)
        self.assertEqual(history[0].previous_hash, GENESIS)
        self.assertEqual(verify(history), history[-1].entry_hash)
        self.assertEqual(append(append((), b"place:1"), b"cancel:1"), history)

    def test_empty_log(self):
        self.assertEqual(verify(()), GENESIS)

    def test_tampered_payload_and_digest_rejected(self):
        log = append(append((), b"a"), b"b")
        for modified in (replace(log[0], payload=b"evil"),
                         replace(log[0], entry_hash="f" * 64)):
            with self.subTest(modified=modified), self.assertRaises(LogIntegrityError):
                verify((modified, log[1]))

    def test_reordered_missing_and_duplicate_entries_rejected(self):
        log = append(append((), b"a"), b"b")
        for history in ((log[1], log[0]), (log[1],), (log[0], log[0])):
            with self.subTest(history=history), self.assertRaises(LogIntegrityError):
                verify(history)

    def test_invalid_input_does_not_change_original(self):
        original = append((), b"a")
        for payload in ("text", bytearray(b"b"), None):
            with self.subTest(payload=payload), self.assertRaises(LogIntegrityError):
                append(original, payload)
        self.assertEqual(verify(original), original[0].entry_hash)

    def test_reject_malformed_sequence_and_hash(self):
        entry = append((), b"a")[0]
        for bad in (0, -1, True, 1.0, 2**64):
            with self.subTest(sequence=bad), self.assertRaises(LogIntegrityError):
                verify((replace(entry, sequence=bad),))
        for bad in ("A" * 64, "0" * 63, "z" * 64):
            with self.subTest(hash=bad), self.assertRaises(LogIntegrityError):
                verify((replace(entry, previous_hash=bad),))

    def test_length_prefix_separates_payloads(self):
        self.assertNotEqual(append((), b"a")[0].entry_hash,
                            append((), b"a\x00")[0].entry_hash)


if __name__ == "__main__":
    unittest.main()

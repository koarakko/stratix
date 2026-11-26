import unittest
from collections import UserDict
from collections.abc import Mapping
from types import MappingProxyType

from services.replication.commit_watermark import (
    QuorumWatermarkError,
    quorum_commit_watermark,
)


class CustomMapping(Mapping):
    def __getitem__(self, key):
        return {"leader": True}[key]

    def __iter__(self):
        return iter(("leader",))

    def __len__(self):
        return 1


class MembershipMappingTests(unittest.TestCase):
    def test_mapping_variants_are_rejected_as_membership(self):
        class DictSubclass(dict):
            pass

        mappings = (
            DictSubclass({"leader": True}),
            UserDict({"leader": True}),
            MappingProxyType({"leader": True}),
            CustomMapping(),
        )
        reports = {"leader": (1, 1)}
        for voters in mappings:
            with self.subTest(mapping_type=type(voters).__name__):
                with self.assertRaises(QuorumWatermarkError):
                    quorum_commit_watermark(voters, reports, term=1)


if __name__ == "__main__":
    unittest.main()

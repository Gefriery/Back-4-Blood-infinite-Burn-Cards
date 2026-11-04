"""Safety checks using synthetic data only; no game or account files are read."""
import copy
import json
import unittest
from pathlib import Path

import burn_cards as tool


class IdentityCrypto:
    def transform(self, data, encrypt=False):
        return data


def encode(profile):
    data = json.dumps(profile, separators=(',', ':')).encode()
    return tool.MAGIC+data+b' '*((-len(data)) % 16)


class RefillSafetyTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            'offlineData': {
                'consumables': {},
                'supplyPoints': {'acquired': 12, 'spent': 3},
                'decks': [{'name': 'Synthetic test deck', 'cards': []}],
                'campaignRuns': [],
            },
            'onlineDataCache': {'synthetic': True},
            'version': 1,
        }
        self.cards = json.loads((Path(__file__).parent/'burn-cards.json').read_text())

    def refill(self, profile=None):
        data, counts = tool.refill(encode(profile or self.profile), IdentityCrypto())
        return json.loads(data[len(tool.MAGIC):].decode()), counts

    def test_changes_only_offline_consumables(self):
        result, counts = self.refill()
        self.assertEqual(len(counts), 27)
        self.assertEqual(len(result['offlineData']['consumables']), 27)
        for value in result['offlineData']['consumables'].values():
            self.assertEqual(value, {'acquired': 999, 'spent': 0})
        result['offlineData']['consumables'] = {}
        self.assertEqual(result, self.profile)

    def test_preserves_spent_and_unrelated_entries(self):
        guid = self.cards[0]['guid']
        entry = 'SyntheticHandle(RowName="'+guid+'")'
        self.profile['offlineData']['consumables'] = {
            entry: {'acquired': 40, 'spent': 7},
            'Synthetic unrelated item': {'acquired': 20, 'spent': 4},
        }
        result, _ = self.refill()
        self.assertEqual(result['offlineData']['consumables'][entry],
                         {'acquired': 1006, 'spent': 7})
        self.assertEqual(result['offlineData']['consumables']['Synthetic unrelated item'],
                         {'acquired': 20, 'spent': 4})

    def test_refill_is_idempotent(self):
        first, _ = self.refill()
        second, _ = self.refill(first)
        self.assertEqual(first, second)

    def test_duplicate_product_handles_rejected(self):
        pattern = 'RowName="'+self.cards[0]['guid']+'"'
        self.profile['offlineData']['consumables'] = {
            'SyntheticA('+pattern+')': {'acquired': 0, 'spent': 0},
            'SyntheticB('+pattern+')': {'acquired': 0, 'spent': 0},
        }
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            self.refill()

    def test_invalid_and_overflowing_counters_rejected(self):
        entry = 'SyntheticHandle(RowName="'+self.cards[0]['guid']+'")'
        for value in ({'acquired': -1, 'spent': 0},
                      {'acquired': True, 'spent': 0},
                      {'acquired': 0, 'spent': 2147483647},
                      {'acquired': 0, 'spent': 0, 'unknown': 0}):
            with self.subTest(value=value):
                profile = copy.deepcopy(self.profile)
                profile['offlineData']['consumables'][entry] = value
                with self.assertRaises(RuntimeError):
                    self.refill(profile)

    def test_unknown_header_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'save format'):
            tool.refill(b'Synthetic invalid save', IdentityCrypto())

    def test_failed_crypto_roundtrip_rejected(self):
        class BrokenCrypto(IdentityCrypto):
            def transform(self, data, encrypt=False):
                return b'wrong' if encrypt else data
        with self.assertRaisesRegex(RuntimeError, 'encryption roundtrip'):
            tool.refill(encode(self.profile), BrokenCrypto())


if __name__ == '__main__':
    unittest.main()

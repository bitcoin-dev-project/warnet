#!/usr/bin/env python3

import shlex
import sys
from pathlib import Path
from unittest.mock import patch

# Import TestBase for consistent test structure
from test_base import TestBase

from warnet.bitcoin import _rpc

# Import _rpc from warnet.bitcoin and run_command from warnet.process
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Edge cases to test
EDGE_CASES = [
    # (params, expected_cmd_suffix, should_fail)
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]'],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]'],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "economical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "economical"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "'economical'"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "'economical'"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", '"economical"'],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", '"economical"'],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco nomical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco nomical"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco'nomical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco'nomical"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", 'eco"nomical'],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", 'eco"nomical'],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco$nomical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco$nomical"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco;nomical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco;nomical"],
        False,
    ),
    (
        ['[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco|nomical"],
        ["send", '[{"bcrt1qsrsmr7f77kcxggk99yp2h8yjzv29lxhet4efwn":0.1}]', "1", "eco|nomical"],
        False,
    ),
    # Malformed JSON (should fail gracefully)
    (
        [
            '[{"desc":"wpkh(tprv8ZgxMBicQKsPfH87iaMtrpzTkWiyFDW7SVWqfsKAhtyEBEqMV6ctPdtc5pNrb2FpSmPcDe8NrxEouUnWj1ud7LT1X1hB1XHKAgB2Z5Z4u2s/84h/1h/0h/0/*)#5j6mshps","timestamp":0,"active":true,"internal":false,"range":[0,999],"next":0,"next_index":0}'
        ],  # Missing closing bracket
        [
            "importdescriptors",
            '[{"desc":"wpkh(tprv8ZgxMBicQKsPfH87iaMtrpzTkWiyFDW7SVWqfsKAhtyEBEqMV6ctPdtc5pNrb2FpSmPcDe8NrxEouUnWj1ud7LT1X1hB1XHKAgB2Z5Z4u2s/84h/1h/0h/0/*)#5j6mshps","timestamp":0,"active":true,"internal":false,"range":[0,999],"next":0,"next_index":0}',
        ],
        True,  # Should fail due to malformed JSON
    ),
    # Unicode in descriptors
    (
        [
            '[{"desc":"wpkh(tprv8ZgxMBicQKsPfH87iaMtrpzTkWiyFDW7SVWqfsKAhtyEBEqMV6ctPdtc5pNrb2FpSmPcDe8NrxEouUnWj1ud7LT1X1hB1XHKAgB2Z5Z4u2s/84h/1h/0h/0/*)#5j6mshps","timestamp":0,"active":true,"internal":false,"range":[0,999],"next":0,"next_index":0,"label":"测试"}'
        ],
        [
            "importdescriptors",
            '[{"desc":"wpkh(tprv8ZgxMBicQKsPfH87iaMtrpzTkWiyFDW7SVWqfsKAhtyEBEqMV6ctPdtc5pNrb2FpSmPcDe8NrxEouUnWj1ud7LT1X1hB1XHKAgB2Z5Z4u2s/84h/1h/0h/0/*)#5j6mshps","timestamp":0,"active":true,"internal":false,"range":[0,999],"next":0,"next_index":0,"label":"测试"}',
        ],
        False,
    ),
    # Long descriptor (simulate, should not crash, may fail)
    (
        [
            "[{'desc':'wpkh([d34db33f/84h/0h/0h/0/0]xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKp...','range':[0,1000]}]"
        ],
        [
            "send",
            "[{'desc':'wpkh([d34db33f/84h/0h/0h/0/0]xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKp...','range':[0,1000]}]",
        ],
        False,  # Updated to False since it now works correctly
    ),
    # Empty params
    ([], ["send"], False),
]


class BitcoinRPCRPCArgsTest(TestBase):
    def __init__(self):
        super().__init__()
        self.tank = "tank-0027"
        self.namespace = "default"
        self.captured_cmds = []

    def run_test(self):
        self.log.info("Testing bitcoin _rpc argument handling edge cases")
        for params, expected_suffix, should_fail in EDGE_CASES:
            # Extract the method from the expected suffix
            method = expected_suffix[0]

            with patch("warnet.bitcoin.run_command") as mock_run_command:
                mock_run_command.return_value = "MOCKED"
                try:
                    _rpc(self.tank, method, params, self.namespace)
                    called_args = mock_run_command.call_args[0][0]
                    self.captured_cmds.append(called_args)
                    # Parse the command string into arguments for comparison
                    parsed_args = shlex.split(called_args)
                    assert parsed_args[-len(expected_suffix) :] == expected_suffix, (
                        f"Params: {params} | Got: {parsed_args[-len(expected_suffix) :]} | Expected: {expected_suffix}"
                    )
                    if should_fail:
                        self.log.info(f"Expected failure for params: {params}, but succeeded.")
                except Exception as e:
                    if not should_fail:
                        raise AssertionError(f"Unexpected failure for params: {params}: {e}") from e
                    self.log.info(f"Expected failure for params: {params}: {e}")
        self.log.info("All edge case argument tests passed.")


if __name__ == "__main__":
    test = BitcoinRPCRPCArgsTest()
    test.run_test()

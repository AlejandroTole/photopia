import struct
import unittest

from apply.writers.sigmoid import (
    SLOT_BASE_PRIMARIES,
    SLOT_COLOR_PROCESSING,
    decode_sigmoid_hex,
    encode_sigmoid,
    pack_sigmoid_params,
    unpack_sigmoid_params,
)


class SigmoidPackingTests(unittest.TestCase):
    def test_enum_slots_round_trip_as_int32(self):
        values = [0.0] * 14
        values[0] = 3.25
        values[5] = 70.53
        values[SLOT_COLOR_PROCESSING] = 1
        values[SLOT_BASE_PRIMARIES] = 4

        packed = pack_sigmoid_params(values)
        decoded = unpack_sigmoid_params(packed)

        self.assertEqual(len(packed), 56)
        self.assertEqual(
            packed[SLOT_COLOR_PROCESSING * 4:SLOT_COLOR_PROCESSING * 4 + 4],
            struct.pack("<i", 1),
        )
        self.assertEqual(
            packed[SLOT_BASE_PRIMARIES * 4:SLOT_BASE_PRIMARIES * 4 + 4],
            struct.pack("<i", 4),
        )
        self.assertEqual(decoded[SLOT_COLOR_PROCESSING], 1)
        self.assertEqual(decoded[SLOT_BASE_PRIMARIES], 4)
        self.assertIs(type(decoded[SLOT_COLOR_PROCESSING]), int)
        self.assertIs(type(decoded[SLOT_BASE_PRIMARIES]), int)
        self.assertEqual(
            packed[0:4],
            struct.pack("<f", values[0]),
        )
        self.assertEqual(
            packed[5 * 4:6 * 4],
            struct.pack("<f", values[5]),
        )

    def test_writer_rejects_enum_values_outside_darktable_ranges(self):
        with self.assertRaisesRegex(ValueError, "slot sigmoid 4"):
            encode_sigmoid({"contrast": 1.0, "color_processing": 2})
        with self.assertRaisesRegex(ValueError, "slot sigmoid 13"):
            encode_sigmoid({"contrast": 1.0, "base_primaries": 5})
        with self.assertRaisesRegex(ValueError, "enum entero"):
            encode_sigmoid({"contrast": 1.0, "color_processing": 1.5})

    def test_reader_rejects_invalid_serialized_enum(self):
        values = [0.0] * 14
        values[SLOT_COLOR_PROCESSING] = 1
        raw = bytearray(pack_sigmoid_params(values))
        raw[SLOT_COLOR_PROCESSING * 4:SLOT_COLOR_PROCESSING * 4 + 4] = struct.pack("<i", 2)

        with self.assertRaisesRegex(ValueError, "slot sigmoid 4"):
            decode_sigmoid_hex(raw.hex())


if __name__ == "__main__":
    unittest.main()

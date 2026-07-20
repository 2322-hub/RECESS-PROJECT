import numpy as np
import pandas as pd
import pytest

from bi_platform.utils.helpers import (
    chunk_dataframe,
    format_number,
    generate_color_palette,
    safe_json_serialize,
)


class TestFormatNumber:
    def test_none(self):
        assert format_number(None) == "N/A"

    def test_small_number(self):
        assert format_number(42) == "42"

    def test_thousands(self):
        # decimals=0 default rounds 1500/1K=2 (no decimal)
        assert format_number(1500) == "2K"
        assert format_number(1500, decimals=1) == "1.5K"

    def test_millions(self):
        assert format_number(2500000) == "2M"
        assert format_number(2500000, decimals=1) == "2.5M"

    def test_negative(self):
        assert format_number(-3000) == "-3K"

    def test_zero(self):
        assert format_number(0) == "0"


class TestGenerateColorPalette:
    def test_exact_count(self):
        palette = generate_color_palette(5)
        assert len(palette) == 5

    def test_large_count(self):
        palette = generate_color_palette(25)
        assert len(palette) == 40  # 20 colors * ceil(25/20)

    def test_zero(self):
        palette = generate_color_palette(0)
        assert len(palette) == 0

    def test_all_hex(self):
        palette = generate_color_palette(3)
        for color in palette:
            assert color.startswith("#")
            assert len(color) == 7


class TestChunkDataframe:
    def test_single_chunk(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        chunks = list(chunk_dataframe(df, chunk_size=10))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_multiple_chunks(self):
        df = pd.DataFrame({"a": range(10)})
        chunks = list(chunk_dataframe(df, chunk_size=3))
        assert len(chunks) == 4
        assert len(chunks[-1]) == 1

    def test_empty(self):
        df = pd.DataFrame({"a": []})
        chunks = list(chunk_dataframe(df, chunk_size=5))
        assert len(chunks) == 0


class TestSafeJsonSerialize:
    def test_numpy_int(self):
        result = safe_json_serialize(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_numpy_float(self):
        result = safe_json_serialize(np.float64(3.14))
        assert result == 3.14
        assert isinstance(result, float)

    def test_numpy_array(self):
        result = safe_json_serialize(np.array([1, 2, 3]))
        assert result == [1, 2, 3]

    def test_pandas_timestamp(self):
        result = safe_json_serialize(pd.Timestamp("2024-01-01"))
        assert result == "2024-01-01T00:00:00"

    def test_pandas_period(self):
        result = safe_json_serialize(pd.Period("2024-01", freq="M"))
        assert isinstance(result, str)

    def test_unserializable(self):
        with pytest.raises(TypeError):
            safe_json_serialize(object())

"""normalizer 測試。"""

import json
import pytest
from pathlib import Path
from scripts.lib.normalizer import normalize, load_aliases, NormalizeResult


@pytest.fixture
def aliases(tmp_path):
    """建立測試用 aliases.json。"""
    data = {
        "songs": {
            "夜に駆ける": ["夜に駆ける", "yoru ni kakeru", "Racing into the Night", "夜にかける"],
            "うっせぇわ": ["うっせぇわ", "usseewa", "うっせえわ"],
            "シャルル": ["シャルル", "Charles", "charles"],
        },
        "artists": {
            "YOASOBI": ["YOASOBI", "yoasobi", "Yoasobi"],
            "Ado": ["Ado", "ado", "アド"],
        },
    }
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return load_aliases(path)


class TestLoadAliases:
    def test_reverse_lookup(self, aliases):
        assert aliases["songs"]["yoru ni kakeru"] == "夜に駆ける"
        assert aliases["songs"]["夜にかける"] == "夜に駆ける"
        assert aliases["artists"]["yoasobi"] == "YOASOBI"

    def test_case_insensitive(self, aliases):
        assert aliases["songs"]["charles"] == "シャルル"
        assert aliases["artists"]["ado"] == "Ado"


class TestNormalize:
    def test_exact_match(self, aliases):
        r = normalize("夜に駆ける", "YOASOBI", aliases)
        assert r == NormalizeResult("夜に駆ける", "YOASOBI", True)

    def test_alias_match(self, aliases):
        r = normalize("yoru ni kakeru", "yoasobi", aliases)
        assert r == NormalizeResult("夜に駆ける", "YOASOBI", True)

    def test_title_only_match(self, aliases):
        r = normalize("うっせえわ", "Unknown Artist", aliases)
        assert r.title == "うっせぇわ"
        assert r.artist == "Unknown Artist"
        assert r.matched is True

    def test_artist_only_match(self, aliases):
        r = normalize("Unknown Song", "アド", aliases)
        assert r.title == "Unknown Song"
        assert r.artist == "Ado"
        assert r.matched is True

    def test_no_match(self, aliases):
        r = normalize("Some Random Song", "Random Artist", aliases)
        assert r.title == "Some Random Song"
        assert r.artist == "Random Artist"
        assert r.matched is False

    def test_nfkc_normalization(self, aliases):
        """全形英數轉半形。"""
        r = normalize("ＹＯＡＳＯＢＩ", "", {"songs": {}, "artists": {}})
        assert r.title == "YOASOBI"

    def test_strip_quotes(self, aliases):
        r = normalize("「夜に駆ける」", "YOASOBI", aliases)
        assert r.title == "夜に駆ける"
        assert r.matched is True

    def test_strip_cover_annotation(self, aliases):
        r = normalize("うっせぇわ(cover)", "Ado", aliases)
        assert r.title == "うっせぇわ"

    def test_strip_short_ver(self, aliases):
        r = normalize("シャルル (short ver.)", "", aliases)
        assert r.title == "シャルル"

    def test_strip_katakana_cover(self, aliases):
        r = normalize("シャルル（カバー）", "", aliases)
        assert r.title == "シャルル"

    def test_whitespace_normalization(self, aliases):
        r = normalize("  夜に駆ける  ", "  YOASOBI  ", aliases)
        assert r.title == "夜に駆ける"
        assert r.artist == "YOASOBI"

    def test_empty_strings(self, aliases):
        r = normalize("", "", aliases)
        assert r.title == ""
        assert r.artist == ""
        assert r.matched is False

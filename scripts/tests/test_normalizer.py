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


def test_feat_without_space_after_period():
    """"feat." の直後に空白が無い書き方も歌手欄から除去する。

    実例: "ジミーサムP feat.初音ミク" が別歌手として取り込まれ、
    既存 27 行の "ジミーサムP" から Calc. が分離した。
    """
    from scripts.lib.normalizer import normalize

    aliases = {"songs": {}, "artists": {}}
    assert normalize("Calc.", "ジミーサムP feat.初音ミク", aliases).artist == "ジミーサムP"
    # 従来どおり空白ありも通る
    assert normalize("X", "19's Sound Factory feat. 初音ミク", aliases).artist == "19's Sound Factory"
    # "feature" で始まる語を誤って切り落とさない
    assert normalize("X", "feature artist", aliases).artist == "feature artist"


def test_artist_paren_gets_a_space():
    """歌手欄の「名前(補足)」は「名前 (補足)」に寄せる。

    曲庫は 52 種が空白あり・12 種が空白なしで、同じ人物が 2 項目に割れていた
    (koyori(電ポルP) / koyori (電ポルP) など)。
    """
    from scripts.lib.normalizer import normalize

    aliases = {"songs": {}, "artists": {}}
    assert normalize("X", "koyori(電ポルP)", aliases).artist == "koyori (電ポルP)"
    # 全角括弧は半角に寄せたうえで空白が入る
    assert normalize("X", "千石撫子（花澤香菜）", aliases).artist == "千石撫子 (花澤香菜)"
    # すでに空白があるものは変えない
    assert normalize("X", "ryo (supercell)", aliases).artist == "ryo (supercell)"
    # 曲名側には掛けない（空白なしが正式表記のものがある）
    assert (
        normalize("我只在乎你(時の流れに身をまかせ)", "", aliases).title
        == "我只在乎你(時の流れに身をまかせ)"
    )

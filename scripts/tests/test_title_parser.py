"""title_parser 測試 — 歌ってみた cover 標題解析。"""

from scripts.lib.title_parser import parse_cover_title


class TestPattern1KamiNoKenzoku:
    """「神の眷属が {曲名} 歌ってみた」模式。"""

    def test_basic(self):
        r = parse_cover_title("神の眷属が ビビデバ 歌ってみた #shorts")
        assert r is not None
        assert r.title == "ビビデバ"
        assert r.is_short is True

    def test_with_wo(self):
        r = parse_cover_title("神の眷属がStellar Stellarを 歌ってみた #歌ってみた #shorts")
        assert r is not None
        assert r.title == "Stellar Stellar"

    def test_with_hashtag_artist(self):
        r = parse_cover_title(
            "神の眷属が シンデレラ 歌ってみた #shorts #歌ってみた #cover #新人vtuber #vsinger #シンデレラ #deco27 #渉海よひら"
        )
        assert r is not None
        assert r.title == "シンデレラ"
        assert r.artist == "deco27"  # 從 hashtag 正確提取原唱

    def test_remix(self):
        r = parse_cover_title("神の眷属が メルト CPK！remix 歌ってみた 【#渉海よひら / 深淵組】")
        assert r is not None
        assert r.title == "メルト CPK！remix"

    def test_with_bracket_suffix(self):
        r = parse_cover_title("神の眷属が クイーンオブハート  #歌ってみた 【#渉海よひら/深淵組】")
        assert r is not None
        assert r.title == "クイーンオブハート"

    def test_no_space_before_name(self):
        r = parse_cover_title("神の眷属がBALALAIKAを 歌ってみた #shorts")
        assert r is not None
        assert r.title == "BALALAIKA"


class TestPattern2BracketUttemita:
    """「【 #歌ってみた 】{曲名}【 VTuber 】」模式。"""

    def test_basic(self):
        r = parse_cover_title("【 #歌ってみた 】ビビデバ【 渉海よひら 】")
        assert r is not None
        assert r.title == "ビビデバ"

    def test_with_emoji(self):
        r = parse_cover_title("【 #歌ってみた 】人間みたいね 【 渉海よひら🫧】")
        assert r is not None
        assert r.title == "人間みたいね"

    def test_with_subtitle(self):
        r = parse_cover_title("【 #歌ってみた 】海の幽霊 - Spirits of the sea 【 渉海よひら🫧】")
        assert r is not None
        assert r.title == "海の幽霊 - Spirits of the sea"

    def test_covered_by(self):
        r = parse_cover_title("【 #歌ってみた  】SOS / covered by 渉海よひら【 シャニマス 】")
        assert r is not None
        assert r.title == "SOS"

    def test_with_ver(self):
        r = parse_cover_title("【 #歌ってみた 】極楽浄土 ( 中文Mix ver. )【 渉海よひら 】")
        assert r is not None
        assert r.title == "極楽浄土 ( 中文Mix ver. )"

    def test_song_slash_artist_in_title(self):
        r = parse_cover_title("【 #歌ってみた 】 ビビデバ/星待すいせい  【 #渉海よひら 深淵組 】")
        assert r is not None
        # この場合、"ビビデバ/星待すいせい" がそのまま取れる
        assert "ビビデバ" in r.title


class TestPattern3NewVtuber:
    """「【 #新人vtuber 】{曲名-歌手}【 VTuber 】歌ってみた」模式。"""

    def test_with_dash_artist(self):
        r = parse_cover_title("【 #新人vtuber 】   極楽浄土-GARNiDELiA    【 渉海よひら 】 歌ってみた")
        assert r is not None
        assert r.title == "極楽浄土"
        assert r.artist == "GARNiDELiA"


class TestPattern4CoverHashtag:
    """「{曲名} cover #shorts #歌ってみた」模式。"""

    def test_basic(self):
        r = parse_cover_title("ビビデバ cover #shorts #歌ってみた #渉海よひら")
        assert r is not None
        assert r.title == "ビビデバ"


class TestNonCover:
    """非 cover 影片應返回 None。"""

    def test_singing_stream(self):
        assert parse_cover_title("【 #歌枠 】SINGING STREAM！初見さん大歓迎！") is None

    def test_regular_stream(self):
        assert parse_cover_title("【 雑談 】おしゃべりしよう！") is None

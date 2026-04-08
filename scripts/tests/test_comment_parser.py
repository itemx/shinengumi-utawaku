"""comment_parser 測試。"""

import pytest
from scripts.lib.comment_parser import (
    parse_comment,
    timestamp_to_seconds,
    pick_best_comment_with_owner,
    SongEntry,
)


class TestTimestampToSeconds:
    def test_mm_ss(self):
        assert timestamp_to_seconds("03:25") == 205

    def test_h_mm_ss(self):
        assert timestamp_to_seconds("1:03:25") == 3805

    def test_zero(self):
        assert timestamp_to_seconds("0:00") == 0

    def test_single_digit_minute(self):
        assert timestamp_to_seconds("3:25") == 205


class TestParseComment:
    def test_basic_setlist(self):
        text = """セトリ
0:03:25 夜に駆ける / YOASOBI
0:08:12 うっせぇわ / Ado
0:15:40 シャルル / バルーン
0:22:00 ドライフラワー / 優里"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 4
        assert songs[0].title_raw == "夜に駆ける"
        assert songs[0].artist_raw == "YOASOBI"
        assert songs[0].seconds == 205
        assert songs[1].title_raw == "うっせぇわ"
        assert songs[1].artist_raw == "Ado"

    def test_bracket_format(self):
        text = """タイムスタンプ
0:05:00 「夜に駆ける」YOASOBI
0:10:00 「うっせぇわ」Ado
0:15:00 「シャルル」バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3
        assert songs[0].title_raw == "夜に駆ける"
        assert songs[0].artist_raw == "YOASOBI"

    def test_no_artist_separator(self):
        text = """セトリ
0:03:25 夜に駆ける
0:08:12 うっせぇわ
0:15:40 シャルル"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3
        assert songs[0].artist_raw == ""

    def test_dash_separator(self):
        text = """0:05:00 Yoru ni Kakeru - YOASOBI
0:10:00 Usseewa - Ado
0:15:00 Charles - Balloon"""
        songs = parse_comment(text)
        assert songs is not None
        assert songs[0].title_raw == "Yoru ni Kakeru"
        assert songs[0].artist_raw == "YOASOBI"

    def test_skip_zero_timestamp(self):
        text = """0:00 配信開始
0:03:25 夜に駆ける / YOASOBI
0:08:12 うっせぇわ / Ado
0:15:40 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3
        assert songs[0].seconds != 0

    def test_less_than_3_songs_returns_none(self):
        text = """0:03:25 夜に駆ける / YOASOBI
0:08:12 うっせぇわ / Ado"""
        assert parse_comment(text) is None

    def test_non_setlist_comment(self):
        text = "今日の配信楽しかったです！ありがとう！"
        assert parse_comment(text) is None

    def test_empty_string(self):
        assert parse_comment("") is None

    def test_with_emoji_decoration(self):
        text = """🎵セトリ🎵
🎤 0:03:25 夜に駆ける / YOASOBI
🎤 0:08:12 うっせぇわ / Ado
🎤 0:15:40 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3

    def test_with_hashtag_lines(self):
        text = """#歌枠 #VTuber
0:03:25 夜に駆ける / YOASOBI
0:08:12 うっせぇわ / Ado
0:15:40 シャルル / バルーン
#セトリ"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3

    def test_h_mm_ss_format(self):
        text = """1:03:25 夜に駆ける / YOASOBI
1:08:12 うっせぇわ / Ado
1:15:40 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert songs[0].seconds == 3805

    def test_fullwidth_separator(self):
        text = """0:03:25 夜に駆ける ／ YOASOBI
0:08:12 うっせぇわ ／ Ado
0:15:40 シャルル ／ バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert songs[0].artist_raw == "YOASOBI"

    def test_mixed_format_real_world(self):
        """實際 VTuber 歌枠留言風格。"""
        text = """今日のセトリ✨

3:25 夜に駆ける / YOASOBI
8:12 うっせぇわ / Ado
15:40 シャルル / バルーン
22:00 ドライフラワー / 優里
28:30 廻廻奇譚 / Eve
35:15 紅蓮華 / LiSA

お疲れ様でした！"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 6


    def test_filter_start_ending_markers(self):
        """スタート/エンディング 配信標記應被過濾。"""
        text = """0:05:00 スタート
0:10:00 夜に駆ける / YOASOBI
0:15:00 うっせぇわ / Ado
0:20:00 シャルル / バルーン
3:00:00 エンディング"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3
        assert all(s.title_raw not in ("スタート", "エンディング") for s in songs)

    def test_filter_talk_segments(self):
        """雜談 timestamp 應被過濾。"""
        text = """0:05:00 夜に駆ける / YOASOBI
0:15:00 ピーチ姫とクッパと配管工兄弟の話
0:20:00 うっせぇわ / Ado
0:30:00 アニメ「ダンダダン」トーク
0:40:00 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3
        assert all("話" not in s.title_raw and "トーク" not in s.title_raw for s in songs)

    def test_long_titles_filtered(self):
        """超長標題（通常是雜談描述）應被過濾。"""
        text = """0:05:00 夜に駆ける / YOASOBI
0:15:00 以前は自分が守る派だったが、守られるも悪くない件について語りたかったのでここで一旦休憩
0:20:00 うっせぇわ / Ado
0:30:00 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 3


    def test_keep_original_songs_without_artist(self):
        """原創曲（無歌手）應被保留，不被過濾。"""
        text = """0:05:00 夜に駆ける / YOASOBI
0:15:00 オリジナル曲タイトル
0:20:00 うっせぇわ / Ado
0:30:00 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        assert len(songs) == 4  # 原創曲保留
        assert any(s.title_raw == "オリジナル曲タイトル" for s in songs)

    def test_filter_long_no_artist_but_keep_short(self):
        """短的無歌手項目保留，長的過濾。"""
        text = """0:05:00 夜に駆ける / YOASOBI
0:10:00 深海の唄
0:15:00 うっせぇわ / Ado
0:20:00 鳥恐怖症の話、しかしペンギンは大体OK、食べるもOK
0:30:00 シャルル / バルーン"""
        songs = parse_comment(text)
        assert songs is not None
        # 「深海の唄」(短) 保留, 「鳥恐怖症の話...」(長+句讀) 過濾
        titles = [s.title_raw for s in songs]
        assert "深海の唄" in titles
        assert not any("鳥恐怖症" in t for t in titles)


class TestPickBestComment:
    def _make_comment(self, text: str, likes: int = 0, author_id: str = "user1"):
        return {
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": text,
                        "likeCount": likes,
                        "authorChannelId": {"value": author_id},
                    }
                }
            }
        }

    def test_picks_most_complete(self):
        short = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z", likes=0
        )
        long = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z\n0:20:00 D / W\n0:25:00 E / V",
            likes=0,
        )
        result = pick_best_comment_with_owner([short, long])
        assert result is not None
        assert len(result) == 5

    def test_likes_as_tiebreaker(self):
        low = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z", likes=0
        )
        high = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z", likes=10
        )
        result = pick_best_comment_with_owner([low, high])
        assert result is not None

    def test_owner_bonus(self):
        user = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z\n0:20:00 D / W",
            likes=5, author_id="user1",
        )
        owner = self._make_comment(
            "0:05:00 A / X\n0:10:00 B / Y\n0:15:00 C / Z",
            likes=0, author_id="owner1",
        )
        # user: 4*2 + 5 = 13, owner: 3*2 + 0 + 10 = 16
        result = pick_best_comment_with_owner([user, owner], channel_owner_id="owner1")
        assert result is not None
        assert len(result) == 3  # owner's version won

    def test_no_valid_comments(self):
        chat = self._make_comment("楽しかった！")
        result = pick_best_comment_with_owner([chat])
        assert result is None

    def test_empty_list(self):
        result = pick_best_comment_with_owner([])
        assert result is None

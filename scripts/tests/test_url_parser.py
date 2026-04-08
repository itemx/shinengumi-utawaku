"""url_parser 測試。"""

import pytest
from scripts.lib.url_parser import parse, UrlParseResult


class TestVideoUrls:
    def test_watch_url(self):
        r = parse("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_watch_url_with_extra_params(self):
        r = parse("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123&list=PLxxxx")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_youtu_be_short(self):
        r = parse("https://youtu.be/dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_live_url(self):
        r = parse("https://www.youtube.com/live/dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_shorts_url(self):
        r = parse("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_bare_video_id(self):
        r = parse("dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_video_id_with_special_chars(self):
        r = parse("abc-_12DE34")
        assert r == UrlParseResult("video", "abc-_12DE34")

    def test_mobile_url(self):
        r = parse("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")


class TestChannelUrls:
    def test_handle_url(self):
        r = parse("https://www.youtube.com/@wadatsumi_yohira")
        assert r == UrlParseResult("channel", "@wadatsumi_yohira")

    def test_channel_id_url(self):
        r = parse("https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx")
        assert r == UrlParseResult("channel", "UCxxxxxxxxxxxxxxxxxxxxxx")

    def test_custom_url(self):
        r = parse("https://www.youtube.com/c/SomeChannel")
        assert r == UrlParseResult("channel", "@SomeChannel")

    def test_bare_handle(self):
        r = parse("@wadatsumi_yohira")
        assert r == UrlParseResult("channel", "@wadatsumi_yohira")

    def test_bare_channel_id(self):
        r = parse("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert r == UrlParseResult("channel", "UCxxxxxxxxxxxxxxxxxxxxxx")


class TestPlaylistUrls:
    def test_playlist_url(self):
        r = parse("https://www.youtube.com/playlist?list=PLxxxxxxxx")
        assert r == UrlParseResult("playlist", "PLxxxxxxxx")

    def test_bare_playlist_id(self):
        r = parse("PLxxxxxxxx")
        assert r == UrlParseResult("playlist", "PLxxxxxxxx")

    def test_uploads_playlist(self):
        r = parse("UUxxxxxxxxxxxxxxxxxxxxxx")
        assert r == UrlParseResult("playlist", "UUxxxxxxxxxxxxxxxxxxxxxx")


class TestEdgeCases:
    def test_whitespace_stripped(self):
        r = parse("  dQw4w9WgXcQ  ")
        assert r == UrlParseResult("video", "dQw4w9WgXcQ")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="空字串"):
            parse("")

    def test_non_youtube_domain_raises(self):
        with pytest.raises(ValueError, match="非 YouTube"):
            parse("https://example.com/watch?v=dQw4w9WgXcQ")

    def test_unrecognized_path_raises(self):
        with pytest.raises(ValueError):
            parse("https://www.youtube.com/some/random/path")

    def test_unrecognized_bare_id_raises(self):
        with pytest.raises(ValueError):
            parse("too_short")

    def test_trailing_slash(self):
        r = parse("https://www.youtube.com/@wadatsumi_yohira/")
        assert r == UrlParseResult("channel", "@wadatsumi_yohira")

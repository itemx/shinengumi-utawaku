"""data_store 測試。"""

import json
import pytest
from scripts.lib.data_store import (
    read_channel_data,
    write_channel_data,
    new_channel_data,
    merge_video,
    get_existing_video_ids,
    read_channels_registry,
    write_channels_registry,
    upsert_channel,
    find_channel,
)


@pytest.fixture
def data_dir(tmp_path):
    """建立測試用資料目錄。"""
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    # 空 channels.json
    (tmp_path / "channels.json").write_text("[]", encoding="utf-8")
    return tmp_path


def _make_video(video_id="vid1", title="Test Stream", songs=None):
    return {
        "videoId": video_id,
        "title": title,
        "publishedAt": "2024-03-15T19:00:00Z",
        "songs": songs or [
            {"timestamp": "3:25", "seconds": 205, "title": "Song A",
             "titleRaw": "Song A", "artist": "Artist X", "artistRaw": "Artist X",
             "url": f"https://youtu.be/{video_id}?t=205"},
        ],
        "sourceCommentId": "comment1",
    }


class TestChannelData:
    def test_read_nonexistent(self, data_dir):
        assert read_channel_data("UCxxx", data_dir) is None

    def test_write_and_read(self, data_dir):
        data = new_channel_data("UCxxx", "Test Channel")
        write_channel_data(data, data_dir)
        loaded = read_channel_data("UCxxx", data_dir)
        assert loaded is not None
        assert loaded["channelId"] == "UCxxx"
        assert loaded["channelName"] == "Test Channel"

    def test_json_formatting(self, data_dir):
        data = new_channel_data("UCxxx", "テストチャンネル")
        write_channel_data(data, data_dir)
        raw = (data_dir / "songs" / "UCxxx.json").read_text(encoding="utf-8")
        # ensure_ascii=False: 日文直接存
        assert "テストチャンネル" in raw
        # indent=2
        assert "  " in raw


class TestMergeVideo:
    def test_add_new_video(self, data_dir):
        data = new_channel_data("UCxxx", "Test")
        video = _make_video("vid1")
        result = merge_video(data, video)
        assert len(result["videos"]) == 1
        assert result["videos"][0]["videoId"] == "vid1"

    def test_duplicate_video_no_duplication(self, data_dir):
        data = new_channel_data("UCxxx", "Test")
        video = _make_video("vid1")
        merge_video(data, video)
        merge_video(data, video)  # 重複
        assert len(data["videos"]) == 1

    def test_merge_new_songs_to_existing_video(self, data_dir):
        data = new_channel_data("UCxxx", "Test")
        video1 = _make_video("vid1", songs=[
            {"timestamp": "3:25", "seconds": 205, "title": "Song A",
             "titleRaw": "Song A", "artist": "X", "artistRaw": "X",
             "url": "https://youtu.be/vid1?t=205"},
        ])
        merge_video(data, video1)

        video2 = _make_video("vid1", songs=[
            {"timestamp": "3:25", "seconds": 205, "title": "Song A",
             "titleRaw": "Song A", "artist": "X", "artistRaw": "X",
             "url": "https://youtu.be/vid1?t=205"},
            {"timestamp": "8:12", "seconds": 492, "title": "Song B",
             "titleRaw": "Song B", "artist": "Y", "artistRaw": "Y",
             "url": "https://youtu.be/vid1?t=492"},
        ])
        merge_video(data, video2)

        assert len(data["videos"]) == 1
        assert len(data["videos"][0]["songs"]) == 2

    def test_multiple_different_videos(self, data_dir):
        data = new_channel_data("UCxxx", "Test")
        merge_video(data, _make_video("vid1"))
        merge_video(data, _make_video("vid2"))
        assert len(data["videos"]) == 2


class TestExistingVideoIds:
    def test_empty_channel(self, data_dir):
        assert get_existing_video_ids("UCxxx", data_dir) == set()

    def test_with_videos(self, data_dir):
        data = new_channel_data("UCxxx", "Test")
        merge_video(data, _make_video("vid1"))
        merge_video(data, _make_video("vid2"))
        write_channel_data(data, data_dir)
        ids = get_existing_video_ids("UCxxx", data_dir)
        assert ids == {"vid1", "vid2"}


class TestChannelsRegistry:
    def test_read_empty(self, data_dir):
        assert read_channels_registry(data_dir) == []

    def test_upsert_new(self, data_dir):
        upsert_channel("UCxxx", "Test Channel", data_dir)
        channels = read_channels_registry(data_dir)
        assert len(channels) == 1
        assert channels[0]["channelId"] == "UCxxx"
        assert channels[0]["name"] == "Test Channel"

    def test_upsert_update(self, data_dir):
        upsert_channel("UCxxx", "Old Name", data_dir)
        upsert_channel("UCxxx", "New Name", data_dir)
        channels = read_channels_registry(data_dir)
        assert len(channels) == 1
        assert channels[0]["name"] == "New Name"

    def test_upsert_with_kwargs(self, data_dir):
        upsert_channel("UCxxx", "Test", data_dir, avatar="https://example.com/img.jpg")
        ch = find_channel("UCxxx", data_dir)
        assert ch is not None
        assert ch["avatar"] == "https://example.com/img.jpg"

    def test_find_nonexistent(self, data_dir):
        assert find_channel("UCxxx", data_dir) is None

    def test_multiple_channels(self, data_dir):
        upsert_channel("UC001", "Channel 1", data_dir)
        upsert_channel("UC002", "Channel 2", data_dir)
        channels = read_channels_registry(data_dir)
        assert len(channels) == 2

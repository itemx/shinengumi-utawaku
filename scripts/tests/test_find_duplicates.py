"""find_duplicates の判定。実データで見つかった表記ゆれをそのまま使う。"""

from scripts.find_duplicates import find, fold


def row(title, artist, title_raw=None, artist_raw=None):
    return {"title": title, "artist": artist,
            "titleRaw": title if title_raw is None else title_raw,
            "artistRaw": artist if artist_raw is None else artist_raw,
            "videoId": "v", "date": "2026-01-01"}


def pairs(rows):
    return {frozenset((c["a"], c["b"])) for c in find(rows)}


def test_fold_ignores_kana_width_case_and_marks():
    assert fold("丸の内サディスティック") == fold("丸ノ内サディスティック")
    assert fold("ヒカリへ") == fold("ヒカリヘ")
    assert fold("Sweets Parade") == fold("sweets parade")
    assert fold("I'm Your") == fold("I’m Your")
    assert fold("美少女無罪♡パイレーツ") == fold("美少女無罪パイレーツ")
    assert fold("träumerei") == fold("traumerei")
    assert fold("が") != fold("か")          # 濁点は落とさない


def test_variant_needs_related_artist():
    rows = [row("丸の内サディスティック", "椎名林檎"), row("丸ノ内サディスティック", "椎名林檎"),
            row("ゴメンねメディスン", "紫咲シオ"), row("ゴメンねメディスン", "紫咲シオン"),
            row("Lemon", "米津玄師"), row("Lemon", "別の歌手")]
    got = pairs(rows)
    assert frozenset((("丸の内サディスティック", "椎名林檎"), ("丸ノ内サディスティック", "椎名林檎"))) in got
    assert frozenset((("ゴメンねメディスン", "紫咲シオ"), ("ゴメンねメディスン", "紫咲シオン"))) in got
    assert not any(("Lemon", "米津玄師") in p for p in got)   # 同名の別の曲は拾わない


def test_stale_only_when_renormalize_just_strips():
    rows = [
        # feat. が後から落ちるようになった古い行 → 拾う
        row("千本桜 feat.初音ミク", "黒うさP"), row("千本桜", "黒うさP"),
        # 入力の歌手が間違っていて人が直した行 → 拾わない
        row("Pray", "水樹奈々", "Pray", "Tommy heavenly6"), row("Pray", "Tommy heavenly6"),
    ]
    got = pairs(rows)
    assert frozenset((("千本桜 feat.初音ミク", "黒うさP"), ("千本桜", "黒うさP"))) in got
    assert not any(("Pray", "水樹奈々") in p for p in got)

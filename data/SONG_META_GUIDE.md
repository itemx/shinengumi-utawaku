# song_meta.json 補完說明 (給 ChatGPT)

`data/song_meta.json` 是一個陣列，每首歌一項：

```json
{ "title": "夜に駆ける", "artist": "YOASOBI", "tags": [], "durationSec": null }
```

請幫每一項補上 `tags` 與 `durationSec`，**不要改動 `title` / `artist`，不要增刪項目**。

## tags（可複選，用下列英文受控字彙，找不到就留空陣列）

只能用這些值（完全一致、小寫），不得自行增加類別：

```
anime  vocaloid  game  tokusatsu  idol  j-pop  k-pop  western  touhou  doujin  original  ballad
```

對照：`anime`=動畫 · `vocaloid`=ボカロ · `game`=遊戲 · `tokusatsu`=特撮 · `idol`=偶像 ·
`j-pop`=日文流行 · `k-pop`=韓流 · `western`=西洋 · `touhou`=東方 · `doujin`=同人 · `original`=原創 · `ballad`=抒情

規則：
- 一首歌可同時屬多類，用 OR。例：某曲既是動畫 OP 又是流行曲 → `["anime", "j-pop"]`。
- 動畫/遊戲/特撮主題歌 → 加對應 tag（`anime` / `game` / `tokusatsu`）。
- VOCALOID／ボカロP 原曲 → `vocaloid`。
- 偶像作品（ラブライブ、デレマス、うたプリ 等）角色曲 → `idol`。
- 日文一般流行曲 → `j-pop`；韓國流行曲 → `k-pop`；西洋歌曲 → `western`。
- 不確定就少加，寧缺勿錯。

## durationSec（原曲錄音室版長度，整數秒）

- 填**原曲的標準版長度**（非現場、非 short），單位秒。例：4 分 21 秒 → `261`。
- 同曲有多個可信正式錄音室標準版時間時，取最長秒數作為排歌 worst case；現場、翻唱、short、remix、instrumental、karaoke、TV/game size 不參與比較。
- 查不到就填 `null`。
- 合理範圍 30–3600 秒；超出視為錯誤。

## 分批

1505 首，請分批處理（例如每批 100–150 首），每批回傳**同格式的 JSON 陣列片段**即可，我會合併。

補完後把結果給我，我會用 `scripts/build_song_meta.py --validate` 檢查 tag 合法性與 duration 範圍，再合併回庫。

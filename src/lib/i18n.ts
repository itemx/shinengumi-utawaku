/**
 * i18n 翻譯系統 — 繁體中文 / 日本語
 */

export type Locale = "zh" | "ja";

export const translations: Record<Locale, Record<string, string>> = {
  zh: {
    // Header
    "nav.home": "首頁",
    // Index
    "index.subtitle": "深淵組成員歌回曲目索引",
    "index.no_channels": "尚未登錄任何頻道",
    "label.streams": "直播",
    "label.covers": "投稿",
    "label.shorts": "Short",
    "label.songs": "曲",
    "label.unique_songs": "曲目",
    "label.performances": "次演唱",
    // Channel page
    "tab.streams": "直播",
    "tab.covers": "投稿動畫",
    "tab.shorts": "Short",
    "tab.songs": "全曲目",
    "tab.missing": "待補",
    "tab.stats": "統計",
    // SongTable
    "table.song": "曲名",
    "table.artist": "歌手",
    "table.count": "次數",
    "btn.shuffle": "隨機播放",
    "search.placeholder": "以曲名或歌手搜尋...",
    // Stats
    "stats.top_songs": "Top 歌曲",
    "stats.top_artists": "Top 歌手",
    // Missing
    "missing.desc": "以下歌枠尚未有 timestamp 歌單，需要手動補充。",
    "missing.label": "待補",
    // Submit page
    "submit.title": "投稿",

    "submit.desc": "貼上 YouTube 影片網址和曲目清單，預覽確認後提交。",
    "submit.url_label": "YouTube URL",
    "submit.setlist_label": "曲目清單（每行一曲）",
    "submit.preview_btn": "預覽解析",
    "submit.preview_title": "解析結果",
    "submit.submit_btn": "提交（建立 Issue）",
    "submit.col_time": "時間",
    "submit.col_song": "曲名",
    "submit.col_artist": "歌手",
    "submit.channel_ok": "頻道已認證",
    "submit.channel_rejected": "此頻道未開放提交",
    "submit.no_video": "請先輸入有效的 YouTube URL",
    "submit.type_label": "類型",
    "submit.type_stream": "直播歌回",
    "submit.type_cover": "投稿動畫",
    "submit.type_original": "原創曲",
    "submit.type_short": "Short",
    "submit.type_unknown": "未知類型",
    "submit.auto_detected": "自動偵測為單曲投稿：",
    "submit.submit_btn_issue": "投稿（建立 Issue）",
    // Song page
    "song.performances": "次演唱",
    // Types
    "type.stream": "直播",
    "type.cover": "投稿",
    "type.short": "Short",
    "type.original": "Original",
    // VideoCard
    "video.youtube": "在 YouTube 觀看",
    "video.songs_unit": "曲",
    // Footer
    "footer.desc": "SEG-V UtaList — 深淵組成員歌回曲目索引",
  },
  ja: {
    "nav.home": "ホーム",
    "index.subtitle": "深淵組メンバー セトリデータベース",
    "index.no_channels": "まだチャンネルが登録されていません",
    "label.streams": "配信",
    "label.covers": "投稿",
    "label.shorts": "Short",
    "label.songs": "曲",
    "label.unique_songs": "曲目",
    "label.performances": "回歌唱",
    "tab.streams": "配信",
    "tab.covers": "投稿動画",
    "tab.shorts": "Short",
    "tab.songs": "全曲目",
    "tab.missing": "未登録",
    "tab.stats": "統計",
    "table.song": "曲名",
    "table.artist": "アーティスト",
    "table.count": "回数",
    "btn.shuffle": "シャッフル",
    "search.placeholder": "曲名・アーティストで検索...",
    "stats.top_songs": "Top 楽曲",
    "stats.top_artists": "Top アーティスト",
    "missing.desc": "以下の歌枠にはまだタイムスタンプセトリがありません。手動で追加が必要です。",
    "missing.label": "未登録",
    "submit.title": "投稿",
    "submit.desc": "YouTube URLとセトリテキストを貼り付けて、プレビュー確認後に投稿してください。",
    "submit.url_label": "YouTube URL",
    "submit.setlist_label": "セトリ（1行1曲）",
    "submit.preview_btn": "プレビュー",
    "submit.preview_title": "解析結果",
    "submit.submit_btn": "投稿（Issue を作成）",
    "submit.col_time": "時間",
    "submit.col_song": "曲名",
    "submit.col_artist": "アーティスト",
    "submit.channel_ok": "チャンネル認証済み",
    "submit.channel_rejected": "このチャンネルは投稿対象外です",
    "submit.no_video": "有効な YouTube URL を入力してください",
    "submit.type_label": "タイプ",
    "submit.type_stream": "配信",
    "submit.type_cover": "投稿動画",
    "submit.type_original": "オリジナル曲",
    "submit.type_short": "Short",
    "submit.type_unknown": "不明",
    "submit.auto_detected": "単曲投稿として自動検出：",
    "submit.submit_btn_issue": "投稿（Issue を作成）",
    "song.performances": "回歌唱",
    "type.stream": "配信",
    "type.cover": "投稿",
    "type.short": "Short",
    "type.original": "Original",
    "video.youtube": "YouTube で見る",
    "video.songs_unit": "曲",
    "footer.desc": "SEG-V UtaList — 深淵組メンバー セトリデータベース",
  },
};

/** Build 時用的預設 locale */
export const defaultLocale: Locale = "zh";

/** Build 時取得翻譯 (server-side) */
export function t(key: string, locale: Locale = defaultLocale): string {
  return translations[locale]?.[key] ?? translations[defaultLocale]?.[key] ?? key;
}

/**
 * 資料讀取 helper — 在 Astro build 時讀取 JSON。
 */
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.join(process.cwd(), "data");

export interface SongEntry {
  timestamp: string;
  seconds: number;
  title: string;
  titleRaw: string;
  artist: string;
  artistRaw: string;
  url: string;
}

export interface VideoEntry {
  videoId: string;
  title: string;
  publishedAt: string;
  songs: SongEntry[];
  sourceCommentId: string;
  type: "stream" | "short" | "cover" | "original";
}

export interface ChannelData {
  channelId: string;
  channelName: string;
  lastFetched: string;
  videos: VideoEntry[];
}

export interface ChannelConfig {
  channelId: string;
  name: string;
  keywords?: string[];
  avatar?: string;
  color?: string;
  colorSecondary?: string;
}

export interface ChannelStats {
  channelId: string;
  channelName: string;
  uniqueSongs: number;
  totalSongs: number;
  totalVideos: number;
  streamCount: number;
  shortCount: number;
  coverCount: number;
  topSongs: {
    title: string;
    artist: string;
    count: number;
    appearances: {
      videoId: string;
      channelId: string;
      date: string;
      title: string;
      url: string;
    }[];
    firstSung: string;
    lastSung: string;
  }[];
  topArtists: { artist: string; count: number }[];
  monthlyActivity: { month: string; count: number }[];
  recentVideos: {
    videoId: string;
    title: string;
    publishedAt: string;
    songCount: number;
  }[];
}

function readJSON<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

export function getChannels(): ChannelConfig[] {
  return readJSON<ChannelConfig[]>(path.join(DATA_DIR, "channels.json"));
}

export function getChannelData(channelId: string): ChannelData | null {
  const filePath = path.join(DATA_DIR, "songs", `${channelId}.json`);
  if (!fs.existsSync(filePath)) return null;
  return readJSON<ChannelData>(filePath);
}

export function getStats(): Record<string, ChannelStats> {
  const filePath = path.join(DATA_DIR, "_stats.json");
  if (!fs.existsSync(filePath)) return {};
  return readJSON<Record<string, ChannelStats>>(filePath);
}

export interface MissingVideo {
  videoId: string;
  title: string;
  publishedAt: string;
  url: string;
}

export function getMissingSetlists(channelId: string): MissingVideo[] {
  const filePath = path.join(DATA_DIR, "missing", `${channelId}.json`);
  if (!fs.existsSync(filePath)) return [];
  const data = readJSON<{
    channelId: string;
    missing: MissingVideo[];
  }>(filePath);
  return data.missing;
}

export function getVideosByType(data: ChannelData) {
  const streams = data.videos.filter((v) => (v.type || "stream") === "stream");
  const shorts = data.videos.filter((v) => v.type === "short");
  const covers = data.videos.filter((v) => v.type === "cover" || v.type === "original");
  return { streams, shorts, covers };
}

/** 收集所有頻道的不重複歌曲 */
export function getAllSongs() {
  const channels = getChannels();
  const songMap = new Map<
    string,
    {
      title: string;
      artist: string;
      count: number;
      appearances: {
        videoId: string;
        channelId: string;
        channelName: string;
        date: string;
        videoTitle: string;
        url: string;
        type: string;
      }[];
    }
  >();

  for (const ch of channels) {
    const data = getChannelData(ch.channelId);
    if (!data) continue;

    for (const video of data.videos) {
      for (const song of video.songs) {
        const key = `${song.title}||${song.artist}`;
        const existing = songMap.get(key);
        const appearance = {
          videoId: video.videoId,
          channelId: data.channelId,
          channelName: data.channelName,
          date: video.publishedAt,
          videoTitle: video.title,
          url: song.url,
          type: video.type || "stream",
        };

        if (existing) {
          existing.count++;
          existing.appearances.push(appearance);
        } else {
          songMap.set(key, {
            title: song.title,
            artist: song.artist,
            count: 1,
            appearances: [appearance],
          });
        }
      }
    }
  }

  return Array.from(songMap.values()).sort((a, b) => b.count - a.count);
}

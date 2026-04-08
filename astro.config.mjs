import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  output: 'static',
  site: 'https://seg-uta.i3x.tw',
  vite: {
    plugins: [tailwindcss()],
  },
});

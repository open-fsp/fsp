import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://openfsp.ru",
  // ignore, а не always: адреса артефактов оканчиваются на .json/.csv/.yaml и слеша не терпят
  trailingSlash: "ignore",
  build: { format: "directory" },
  integrations: [sitemap({ filter: (page) => !page.includes("/1.0/") })],
  vite: {
    // реестры и схемы лежат выше каталога сайта: читаются на этапе сборки
    server: { fs: { allow: [".."] } },
  },
});

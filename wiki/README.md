# Wiki source

These files are the source of the [GitHub wiki](https://github.com/phanivvk25/Koyala/wiki). Edit them here, review them in a pull request, then publish.

## Publish

GitHub creates the wiki repository only after the first page is saved on the website:

1. Open https://github.com/phanivvk25/Koyala/wiki and click **Create the first page** → **Save page** (content doesn't matter; it will be replaced).
2. From the repo root, run:
   ```bash
   ./wiki/publish.sh
   ```

Page names come from file names (`Getting-Started.md` → **Getting Started**). `_Sidebar.md` and `_Footer.md` appear on every page. This README is not published.

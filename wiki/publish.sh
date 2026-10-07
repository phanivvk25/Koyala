#!/usr/bin/env bash
# Publish wiki/*.md to the GitHub wiki. Run from the repo root.
set -euo pipefail

REPO_URL="${WIKI_REPO_URL:-https://github.com/phanivvk25/Koyala.wiki.git}"
SRC="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone --quiet "$REPO_URL" "$TMP/wiki" || {
  echo "Could not clone $REPO_URL." >&2
  echo "Create the first wiki page on GitHub first (see wiki/README.md)." >&2
  exit 1
}

# Replace all pages with the source of truth in this folder.
find "$TMP/wiki" -maxdepth 1 -name '*.md' -delete
for f in "$SRC"/*.md; do
  [ "$(basename "$f")" = "README.md" ] && continue
  cp "$f" "$TMP/wiki/"
done

cd "$TMP/wiki"
git add -A
if git diff --cached --quiet; then
  echo "Wiki already up to date."
  exit 0
fi
git commit --quiet -m "Update wiki from $(git -C "$SRC/.." rev-parse --short HEAD)"
git push --quiet
echo "Wiki published: ${REPO_URL%.wiki.git}/wiki"

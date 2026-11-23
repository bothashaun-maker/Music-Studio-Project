#!/usr/bin/env bash
# Push the /home/z/my-project workspace repo to GitHub as a private repo.
# Usage: GITHUB_TOKEN=ghp_xxx bash /home/z/my-project/scripts/push-to-github.sh
# Needs a classic PAT with the "repo" scope. The token is never stored on disk.
set -euo pipefail

: "${GITHUB_TOKEN:?Set GITHUB_TOKEN first: GITHUB_TOKEN=ghp_... bash $0}"
REPO_NAME="${REPO_NAME:-my-project}"

cd /home/z/my-project

OWNER=$(curl -fsS -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['login'])")
echo "GitHub account: $OWNER"

# Create the repo if it does not exist yet (private).
if ! curl -fsS -o /dev/null -H "Authorization: Bearer $GITHUB_TOKEN" \
     "https://api.github.com/repos/$OWNER/$REPO_NAME"; then
  echo "Creating private repo $OWNER/$REPO_NAME ..."
  curl -fsS -o /dev/null -X POST \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_NAME\",\"private\":true,\"description\":\"Workspace snapshot: Music fix 2026-11-23 (+ Movies, pins, canvases)\"}"
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:$GITHUB_TOKEN@github.com/$OWNER/$REPO_NAME.git"
git push -u origin main
# Strip the token back out of .git/config after a successful push.
git remote set-url origin "https://github.com/$OWNER/$REPO_NAME.git"

echo
echo "Done: https://github.com/$OWNER/$REPO_NAME"

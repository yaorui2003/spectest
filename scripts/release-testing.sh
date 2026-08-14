#!/usr/bin/env bash
# release-testing.sh — 一键发布 testing 扩展 + testing-tdd 预设到 yaorui2003/spectest
#
# 用法:
#   GH_TOKEN=<token> scripts/release-testing.sh            # 版本取自 extension.yml
#   GH_TOKEN=<token> scripts/release-testing.sh 1.1.2      # 显式指定版本
#   scripts/release-testing.sh --dry-run                   # 只打包不发布
#
# 流程: 打包 zip(保留脚本可执行位) -> git tag + push backup -> 创建 GitHub
# Release -> 上传两个 zip 资产。幂等: Release/tag 已存在时复用, 资产已存在时跳过。
set -euo pipefail

REPO="yaorui2003/spectest"
REMOTE="backup"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$ROOT/extensions/testing"
PRESET_DIR="$ROOT/presets/testing-tdd"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ---- 版本: 显式参数优先, 否则读 extension.yml ----
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  VERSION="$(sed -n 's/^[[:space:]]*version:[[:space:]]*\([0-9][0-9.]*\).*/\1/p' "$EXT_DIR/extension.yml" | head -1)"
fi
if [ -z "$VERSION" ]; then
  echo "错误: 无法确定版本号 (传参或从 $EXT_DIR/extension.yml 读取)" >&2
  exit 1
fi
TAG="v$VERSION"
echo "==> 发布 $TAG ($REPO)"

# ---- 打包 (python, 保留脚本可执行位, manifest 位于 zip 根) ----
pack() {
  python3 - "$1" "$2" <<'PY'
import sys, zipfile
from pathlib import Path
src, out = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        st = p.stat()
        mode = 0o755 if st.st_mode & 0o111 else 0o644
        info = zipfile.ZipInfo(p.relative_to(src).as_posix(), (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = mode << 16
        z.writestr(info, p.read_bytes())
PY
}
EXT_ZIP="$WORK/testing-$VERSION.zip"
PRESET_ZIP="$WORK/testing-tdd-$VERSION.zip"
echo "==> 打包 $EXT_ZIP"
pack "$EXT_DIR" "$EXT_ZIP"
echo "==> 打包 $PRESET_ZIP"
pack "$PRESET_DIR" "$PRESET_ZIP"
for f in "$EXT_ZIP" "$PRESET_ZIP"; do
  python3 - "$f" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
need = "extension.yml" if "extension.yml" in names else "preset.yml"
assert need in names, f"{sys.argv[1]} 缺少根级 {need}"
print(f"   ok: {sys.argv[1]} ({len(names)} files, 根含 {need})")
PY
done

# ---- tag + push ----
cd "$ROOT"
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "==> tag $TAG 已存在, 跳过"
else
  if [ "$DRY_RUN" = 1 ]; then
    echo "==> [dry-run] 将打 tag $TAG 并 push $REMOTE"
  else
    git tag "$TAG"
    git push "$REMOTE" "$TAG"
  fi
fi

if [ "$DRY_RUN" = 1 ]; then
  echo "==> [dry-run] 完成, 未发布。zip 位于: $EXT_ZIP $PRESET_ZIP"
  exit 0
fi

# ---- GitHub Release (需要 GH_TOKEN) ----
if [ -z "${GH_TOKEN:-}" ]; then
  echo "错误: 未设置 GH_TOKEN (GitHub PAT, 需 repo 权限)。export GH_TOKEN=... 后重跑" >&2
  exit 1
fi
API="https://api.github.com/repos/$REPO"
UPLOAD="https://uploads.github.com/repos/$REPO"
AUTH=(-H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")

echo "==> 检查是否已有 Release $TAG"
EXISTING="$(curl -fsS "${AUTH[@]}" "$API/releases/tags/$TAG" 2>/dev/null || true)"
RELEASE_ID="$(printf '%s' "$EXISTING" | python3 -c 'import sys,json
try: print(json.load(sys.stdin)["id"])
except Exception: print("")')"

if [ -n "$RELEASE_ID" ]; then
  echo "==> Release 已存在 (id=$RELEASE_ID), 复用"
else
  echo "==> 创建 Release $TAG"
  BODY="testing 扩展 + testing-tdd 预设 v$VERSION。安装见 extensions/testing/README.md：\n\n    specify extension add testing --from https://github.com/$REPO/releases/download/$TAG/testing-$VERSION.zip\n    specify preset add testing-tdd --from https://github.com/$REPO/releases/download/$TAG/testing-tdd-$VERSION.zip\n\n卸载(切回普通 spec-kit): specify preset remove testing-tdd && specify extension remove testing"
  RESP="$(curl -fsS "${AUTH[@]}" -X POST "$API/releases" \
    -d "$(python3 -c 'import json,sys
print(json.dumps({"tag_name": sys.argv[1], "name": sys.argv[1], "body": sys.argv[2]}))' "$TAG" "$BODY")")"
  RELEASE_ID="$(printf '%s' "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
  echo "==> Release 创建成功 (id=$RELEASE_ID)"
fi

# ---- 上传资产 (已存在则跳过) ----
upload_asset() {
  local file="$1" name="$(basename "$1")"
  echo "==> 上传 $name"
  if ! curl -fsS "${AUTH[@]}" -X POST "$UPLOAD/releases/$RELEASE_ID/assets?name=$name" \
      -H "Content-Type: application/zip" --data-binary @"$file" >/dev/null 2>&1; then
    if curl -fsS "${AUTH[@]}" "$API/releases/$RELEASE_ID/assets" 2>/dev/null \
        | python3 -c "import sys,json; sys.exit(0 if any(a['name']=='$name' for a in json.load(sys.stdin)) else 1)"; then
      echo "   资产 $name 已存在, 跳过"
    else
      echo "   警告: 上传 $name 失败" >&2
    fi
  else
    echo "   已上传 $name"
  fi
}
upload_asset "$EXT_ZIP"
upload_asset "$PRESET_ZIP"

echo ""
echo "==> 完成: https://github.com/$REPO/releases/tag/$TAG"

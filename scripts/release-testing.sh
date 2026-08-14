#!/usr/bin/env bash
# release-testing.sh — 一键发布 testing 扩展 + testing-tdd 预设到 yaorui2003/spectest
#
# 用法:
#   GH_TOKEN=<token> scripts/release-testing.sh            # 版本取自 extension.yml
#   GH_TOKEN=<token> scripts/release-testing.sh 1.1.2      # 显式指定版本
#   scripts/release-testing.sh --dry-run                   # 只打包不发布
#
# 流程: 打包 zip(保留脚本可执行位) -> git tag + push backup -> 发布产物。
# 发布双模式(自动选择):
#   * Release 模式: github.com 可达时, 用 REST API 创建 GitHub Release 并上传资产,
#     URL: https://github.com/yaorui2003/spectest/releases/download/<tag>/<zip>
#   * 仓库模式:    github.com 不可达(如大陆网络被墙)时, 把 zip 提交进 releases/ 目录,
#     URL: https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/<zip>
# 幂等: tag/Release 已存在时复用, 资产已存在时跳过。
set -euo pipefail

REPO="yaorui2003/spectest"
REMOTE="backup"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$ROOT/extensions/testing"
PRESET_DIR="$ROOT/presets/testing-tdd"
RELEASES_DIR="$ROOT/releases"
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

# ---- 网络检测: github.com 可达则 Release 模式, 否则仓库模式 ----
if [ "$DRY_RUN" = 1 ]; then
  echo "==> [dry-run] 完成, 未发布。zip 位于: $EXT_ZIP $PRESET_ZIP"
  exit 0
fi

if curl -fsS -m 5 -o /dev/null "https://github.com/" 2>/dev/null; then
  MODE="release"
else
  MODE="repo"
fi
echo "==> 网络检测: github.com 可达=$([ "$MODE" = release ] && echo 是 || echo 否), 使用 [${MODE}] 模式"

# ================= 仓库模式: zip 提交进 releases/ + raw 下载 =================
if [ "$MODE" = "repo" ]; then
  cp "$EXT_ZIP" "$PRESET_ZIP" "$RELEASES_DIR/"
  git add "$RELEASES_DIR"
  if git diff --cached --quiet; then
    echo "==> releases/ 无变化, 跳过 commit"
  else
    git commit -m "chore(releases): ship testing-$VERSION.zip + testing-tdd-$VERSION.zip"
    git push "$REMOTE" main
  fi
  echo ""
  echo "==> 完成(仓库模式)"
  echo "安装:"
  echo "  specify extension add testing --from https://raw.githubusercontent.com/$REPO/main/releases/testing-$VERSION.zip"
  echo "  specify preset add testing-tdd --from https://raw.githubusercontent.com/$REPO/main/releases/testing-tdd-$VERSION.zip"
  echo "卸载(切回普通 spec-kit): specify preset remove testing-tdd && specify extension remove testing"
  exit 0
fi

# ================= Release 模式: REST API 创建 Release + 上传资产 =================
if [ -z "${GH_TOKEN:-}" ]; then
  echo "错误: 未设置 GH_TOKEN (GitHub PAT, 需 repo 权限)。export GH_TOKEN=... 后重跑" >&2
  exit 1
fi
API="https://api.github.com/repos/$REPO"
UPLOAD="https://uploads.github.com/repos/$REPO"
AUTH=(-H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")

# 部分网络 api.github.com / uploads.github.com 被 DNS 污染, 分别探测可用 IP 并 --resolve
resolve_api=()
resolve_up=()
if ! curl -fsS -m 5 -o /dev/null "https://api.github.com/zen" 2>/dev/null; then
  for ip in 140.82.112.6 140.82.113.6 140.82.114.6 140.82.116.6; do
    if curl -fsS -m 5 --resolve "api.github.com:443:$ip" -o /dev/null "https://api.github.com/zen" 2>/dev/null; then
      resolve_api=(--resolve "api.github.com:443:$ip"); break
    fi
  done
  [ ${#resolve_api[@]} -gt 0 ] || { echo "错误: 无法连接 api.github.com" >&2; exit 1; }
  echo "==> api.github.com 使用 $ip 绕过 DNS 污染"
fi
if ! curl -fsS -m 5 -o /dev/null "https://uploads.github.com/" 2>/dev/null; then
  for ip in 140.82.112.3 140.82.113.3 140.82.114.3 140.82.116.3 140.82.112.4 140.82.113.4; do
    code="$(curl -sS -m 5 -o /dev/null -w "%{http_code}" --resolve "uploads.github.com:443:$ip" "https://uploads.github.com/" 2>/dev/null || true)"
    if [ -n "$code" ] && [ "$code" != "000" ]; then
      resolve_up=(--resolve "uploads.github.com:443:$ip"); break
    fi
  done
  [ ${#resolve_up[@]} -gt 0 ] || { echo "错误: 无法连接 uploads.github.com" >&2; exit 1; }
  echo "==> uploads.github.com 使用 $ip 绕过 DNS 污染"
fi

echo "==> 检查是否已有 Release $TAG"
EXISTING="$(curl -fsS "${resolve_api[@]}" "${AUTH[@]}" "$API/releases/tags/$TAG" 2>/dev/null || true)"
RELEASE_ID="$(printf '%s' "$EXISTING" | python3 -c 'import sys,json
try: print(json.load(sys.stdin)["id"])
except Exception: print("")')"

if [ -n "$RELEASE_ID" ]; then
  echo "==> Release 已存在 (id=$RELEASE_ID), 复用"
else
  echo "==> 创建 Release $TAG"
  BODY="testing 扩展 + testing-tdd 预设 v$VERSION。安装见 extensions/testing/README.md：\n\n    specify extension add testing --from https://github.com/$REPO/releases/download/$TAG/testing-$VERSION.zip\n    specify preset add testing-tdd --from https://github.com/$REPO/releases/download/$TAG/testing-tdd-$VERSION.zip\n\n卸载(切回普通 spec-kit): specify preset remove testing-tdd && specify extension remove testing"
  RESP="$(curl -fsS "${resolve_api[@]}" "${AUTH[@]}" -X POST "$API/releases" \
    -d "$(python3 -c 'import json,sys
print(json.dumps({"tag_name": sys.argv[1], "name": sys.argv[1], "body": sys.argv[2]}))' "$TAG" "$BODY")")"
  RELEASE_ID="$(printf '%s' "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
  echo "==> Release 创建成功 (id=$RELEASE_ID)"
fi

# ---- 上传资产 (跟随 301 重定向; 已存在则跳过) ----
upload_asset() {
  local file="$1" name="$(basename "$1")"
  echo "==> 上传 $name"
  if curl -fsSL -m 120 --post302 "${resolve_up[@]}" "${AUTH[@]}" \
      -H "Content-Type: application/octet-stream" \
      --data-binary @"$file" \
      -X POST "$UPLOAD/releases/$RELEASE_ID/assets?name=$name" >/dev/null 2>&1; then
    echo "   已上传 $name"
  else
    if curl -fsS "${resolve_api[@]}" "${AUTH[@]}" "$API/releases/$RELEASE_ID/assets" 2>/dev/null \
        | python3 -c "import sys,json; sys.exit(0 if any(a['name']=='$name' for a in json.load(sys.stdin)) else 1)"; then
      echo "   资产 $name 已存在, 跳过"
    else
      echo "   警告: 上传 $name 失败 (github.com 不可达时请改用仓库模式: 用 --dry-run 外的网络, 或手动把 zip 提交进 releases/)" >&2
    fi
  fi
}
upload_asset "$EXT_ZIP"
upload_asset "$PRESET_ZIP"

echo ""
echo "==> 完成: https://github.com/$REPO/releases/tag/$TAG"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_and_summarize.py
=========================
폴더 내 파일을 유형별로 분류·복사하고, 텍스트를 추출하여
Antigravity 에이전트가 AI 요약을 수행할 수 있도록 준비하는 스크립트.

사용법:
  python classify_and_summarize.py <원본폴더> <결과폴더> [--ai claude|gemini|gpt]

동작:
  1. 원본 폴더를 재귀 스캔하여 파일 목록 수집
  2. 확장자 기반으로 카테고리(documents, presentations, web, code 등) 분류
  3. 결과 폴더 아래에 카테고리 하위 폴더를 생성하고 파일 복사 (원본 유지)
  4. 텍스트 추출 가능한 파일은 내용을 추출하여 JSON manifest 저장
  5. 에이전트가 manifest를 읽고 AI 모델로 요약 및 Mermaid 다이어그램 생성
"""

import os
import sys
import json
import shutil
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime


# ──────────────────────────────────────────────
# 파일 분류 카테고리 정의
# ──────────────────────────────────────────────
CATEGORIES = {
    "documents": {
        "extensions": [".docx", ".doc", ".pdf", ".txt", ".rtf", ".odt"],
        "label": "📄 문서 (Documents)",
    },
    "presentations": {
        "extensions": [".pptx", ".ppt", ".odp", ".key"],
        "label": "📊 프레젠테이션 (Presentations)",
    },
    "spreadsheets": {
        "extensions": [".xlsx", ".xls", ".csv", ".ods"],
        "label": "📈 스프레드시트 (Spreadsheets)",
    },
    "web": {
        "extensions": [".html", ".htm", ".xhtml", ".mhtml"],
        "label": "🌐 웹 문서 (Web)",
    },
    "markup": {
        "extensions": [".md", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        "label": "📝 마크업/설정 (Markup & Config)",
    },
    "code": {
        "extensions": [
            ".py", ".c", ".h", ".cpp", ".hpp", ".java", ".js", ".ts",
            ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".kt",
            ".sh", ".bash", ".bat", ".ps1", ".lua", ".r", ".m",
        ],
        "label": "💻 소스코드 (Code)",
    },
    "images": {
        "extensions": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp", ".tif", ".tiff"],
        "label": "🖼️ 이미지 (Images)",
    },
    "archives": {
        "extensions": [".zip", ".tar", ".gz", ".7z", ".rar", ".bz2"],
        "label": "📦 압축파일 (Archives)",
    },
}

# 확장자 → 카테고리 역매핑
_EXT_MAP = {}
for cat, info in CATEGORIES.items():
    for ext in info["extensions"]:
        _EXT_MAP[ext] = cat


def classify_extension(ext: str) -> str:
    """확장자를 카테고리 이름으로 매핑. 없으면 'others'"""
    return _EXT_MAP.get(ext.lower(), "others")


# ──────────────────────────────────────────────
# 텍스트 추출 (HTML, DOCX, PPTX, 일반 텍스트)
# ──────────────────────────────────────────────
class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._hide = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "head", "noscript"}:
            self._hide = True
        elif tag.lower() in {"p", "div", "br", "tr", "li"}:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "head", "noscript"}:
            self._hide = False

    def handle_data(self, data):
        if not self._hide:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts).strip()


def _read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def extract_html(path: Path) -> str:
    raw = _read_text(path)
    if not raw:
        return ""
    p = _HTMLText()
    p.feed(raw)
    return p.text()


def extract_docx(path: Path) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist():
                return ""
            tree = ET.fromstring(z.read("word/document.xml"))
            body = tree.find("w:body", ns)
            if body is None:
                return ""
            parts = []
            for child in body:
                if child.tag.endswith("}p"):
                    texts = [t.text for t in child.iter(f"{{{ns['w']}}}t") if t.text]
                    line = "".join(texts).strip()
                    if line:
                        parts.append(line)
                elif child.tag.endswith("}tbl"):
                    for row in child.iter(f"{{{ns['w']}}}tr"):
                        cells = []
                        for cell in row.iter(f"{{{ns['w']}}}tc"):
                            ct = "".join(t.text for t in cell.iter(f"{{{ns['w']}}}t") if t.text)
                            cells.append(ct.strip())
                        if cells:
                            parts.append("| " + " | ".join(cells) + " |")
            return "\n".join(parts)
    except Exception:
        return ""


def extract_pptx(path: Path) -> str:
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    try:
        with zipfile.ZipFile(path) as z:
            slides = sorted(
                [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            )
            parts = []
            for idx, sf in enumerate(slides, 1):
                tree = ET.fromstring(z.read(sf))
                texts = []
                for p in tree.iter(f"{{{ns_a}}}p"):
                    seg = "".join(t.text for t in p.iter(f"{{{ns_a}}}t") if t.text).strip()
                    if seg:
                        texts.append(seg)
                if texts:
                    parts.append(f"[슬라이드 {idx}] {texts[0]}")
                    parts.extend(f"  - {t}" for t in texts[1:])
            return "\n".join(parts)
    except Exception:
        return ""


def extract_content(path: Path) -> str:
    """파일 확장자에 따라 텍스트 내용 추출. 추출 불가 시 빈 문자열."""
    ext = path.suffix.lower()
    if ext in (".html", ".htm", ".xhtml", ".mhtml"):
        return extract_html(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pptx":
        return extract_pptx(path)
    if ext == ".pdf":
        return "(PDF 파일 – 에이전트가 직접 분석 필요)"
    # 이미지, 압축 등 바이너리는 건너뜀
    if ext in _EXT_MAP and classify_extension(ext) in ("images", "archives"):
        return ""
    # 나머지는 텍스트로 시도
    content = _read_text(path)
    # 바이너리 감지: NULL 바이트가 있으면 건너뜀
    if "\x00" in content[:4096]:
        return ""
    return content


# ──────────────────────────────────────────────
# 메인 로직
# ──────────────────────────────────────────────
def scan_and_classify(source_dir: Path):
    """원본 폴더를 재귀 스캔하여 파일 목록과 카테고리를 반환."""
    results = []
    for root, _dirs, files in os.walk(source_dir):
        for fname in files:
            fpath = Path(root) / fname
            if not fpath.is_file():
                continue
            ext = fpath.suffix.lower()
            cat = classify_extension(ext)
            rel = fpath.relative_to(source_dir)
            results.append({
                "source": str(fpath),
                "relative": str(rel),
                "filename": fname,
                "extension": ext,
                "category": cat,
                "size_bytes": fpath.stat().st_size,
            })
    return results


def copy_files(file_list: list[dict], output_dir: Path):
    """분류 결과에 따라 카테고리 폴더로 파일 복사."""
    for item in file_list:
        cat = item["category"]
        dest_dir = output_dir / cat
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = Path(item["source"])
        dest = dest_dir / item["filename"]
        # 동일 이름 충돌 방지
        if dest.exists():
            stem = src.stem
            suffix = src.suffix
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        shutil.copy2(src, dest)
        item["copied_to"] = str(dest)


def extract_texts(file_list: list[dict]):
    """각 파일에서 텍스트 추출 결과를 file_list 에 추가."""
    for item in file_list:
        src = Path(item["source"])
        content = extract_content(src)
        # 너무 큰 텍스트는 잘라둠 (200KB)
        if len(content) > 200_000:
            content = content[:200_000] + "\n\n... (이하 생략, 원본 파일 참조)"
        item["extracted_text"] = content
        item["has_text"] = bool(content.strip())


def build_manifest(file_list: list[dict], source_dir: str, output_dir: str, ai_model: str) -> dict:
    """에이전트가 읽을 manifest JSON 구성."""
    # 카테고리별 통계
    stats = {}
    for item in file_list:
        cat = item["category"]
        stats.setdefault(cat, {"count": 0, "total_bytes": 0})
        stats[cat]["count"] += 1
        stats[cat]["total_bytes"] += item["size_bytes"]

    return {
        "created_at": datetime.now().isoformat(),
        "source_folder": source_dir,
        "output_folder": output_dir,
        "ai_model": ai_model,
        "total_files": len(file_list),
        "category_stats": stats,
        "files": file_list,
    }


def main():
    parser = argparse.ArgumentParser(
        description="파일 분류 & 텍스트 추출 도구 (Antigravity 에이전트 연동용)"
    )
    parser.add_argument("source", help="원본 파일이 있는 폴더 경로")
    parser.add_argument("output", help="분류 결과를 저장할 폴더 경로")
    parser.add_argument(
        "--ai", choices=["claude", "gemini", "gpt"], default="gemini",
        help="요약에 사용할 AI 모델 (기본값: gemini)"
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output).resolve()

    if not source_dir.is_dir():
        print(f"[오류] 원본 폴더를 찾을 수 없습니다: {source_dir}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("  📂 파일 분류 & 텍스트 추출 도구")
    print("=" * 60)
    print(f"  원본 폴더 : {source_dir}")
    print(f"  결과 폴더 : {output_dir}")
    print(f"  선택 AI   : {args.ai}")
    print("=" * 60)

    # 1) 스캔 & 분류
    print("\n[1/4] 원본 폴더 스캔 중...")
    file_list = scan_and_classify(source_dir)
    if not file_list:
        print("  파일을 찾을 수 없습니다.")
        sys.exit(0)
    print(f"  → {len(file_list)}개 파일 발견")

    # 카테고리별 현황
    cat_counts = {}
    for f in file_list:
        cat_counts[f["category"]] = cat_counts.get(f["category"], 0) + 1
    for cat, cnt in sorted(cat_counts.items()):
        label = CATEGORIES.get(cat, {}).get("label", f"📁 {cat}")
        print(f"    {label}: {cnt}개")

    # 2) 파일 복사
    print("\n[2/4] 카테고리별 폴더로 파일 복사 중...")
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_files(file_list, output_dir)
    print(f"  → {len(file_list)}개 파일 복사 완료")

    # 3) 텍스트 추출
    print("\n[3/4] 텍스트 내용 추출 중...")
    extract_texts(file_list)
    text_count = sum(1 for f in file_list if f.get("has_text"))
    print(f"  → {text_count}개 파일에서 텍스트 추출 성공")

    # 4) manifest 저장
    print("\n[4/4] manifest 파일 저장 중...")
    manifest = build_manifest(file_list, str(source_dir), str(output_dir), args.ai)
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  → {manifest_path}")

    # 분류 요약 리포트
    report_path = output_dir / "_classification_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 📂 파일 분류 리포트\n\n")
        f.write(f"- **원본 폴더**: `{source_dir}`\n")
        f.write(f"- **결과 폴더**: `{output_dir}`\n")
        f.write(f"- **선택 AI**: `{args.ai}`\n")
        f.write(f"- **생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **총 파일 수**: {len(file_list)}개\n\n")

        f.write("## 카테고리별 분류 현황\n\n")
        f.write("| 카테고리 | 파일 수 | 폴더 |\n")
        f.write("|----------|---------|-------|\n")
        for cat, cnt in sorted(cat_counts.items()):
            label = CATEGORIES.get(cat, {}).get("label", cat)
            f.write(f"| {label} | {cnt} | `{cat}/` |\n")

        f.write("\n## 파일 목록\n\n")
        for cat in sorted(cat_counts.keys()):
            label = CATEGORIES.get(cat, {}).get("label", f"📁 {cat}")
            f.write(f"\n### {label}\n\n")
            cat_files = [item for item in file_list if item["category"] == cat]
            for item in cat_files:
                size_kb = item["size_bytes"] / 1024
                has_text = "✅" if item.get("has_text") else "❌"
                f.write(f"- `{item['filename']}` ({size_kb:.1f} KB) — 텍스트 추출: {has_text}\n")

        # Mermaid 분류 다이어그램
        f.write("\n## 분류 구조 다이어그램\n\n")
        f.write("```mermaid\nflowchart TD\n")
        f.write(f'    SRC["원본 폴더"]\n')
        for i, (cat, cnt) in enumerate(sorted(cat_counts.items())):
            label = CATEGORIES.get(cat, {}).get("label", cat).split("(")[0].strip()
            node_id = f"C{i}"
            f.write(f'    {node_id}["{label} ({cnt}개)"]\n')
            f.write(f"    SRC --> {node_id}\n")
        f.write("```\n")

    print(f"  → {report_path}")

    print("\n" + "=" * 60)
    print("  ✅ 파일 분류 완료!")
    print(f"  manifest : {manifest_path}")
    print(f"  리포트   : {report_path}")
    print("=" * 60)
    print("\n에이전트가 _manifest.json을 읽어 AI 요약을 수행합니다.")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline Multi-format File Summarizer (No API Key Required)
--------------------------------------------------------
이 스크립트는 Gemini API 키가 없을 때도 동작하도록 설계되었습니다.
HTML, DOCX, PPTX, TXT/MD 등 텍스트 기반 파일을 분석하고, 간단한
핵심 요약과 구조화된 **Mermaid 흐름도**를 자동 생성합니다.

⚠️ 제한 사항
- PDF 파일은 외부 API 없이 텍스트 추출이 불가능하므로 "PDF는 지원되지 않음" 메시지만 표시합니다.
- 요약은 고급 AI 모델이 아니라 **휴리스틱(규칙 기반) 요약**이며, 정확도는 제한적입니다.
- Mermaid 다이어그램은 문서에 포함된 헤딩(제목) 순서를 기반으로 간단한 흐름도(`flowchart TD`)를 생성합니다.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

# ---------- HTML 텍스트 추출 ----------
class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.hide = False
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "head", "noscript"}:
            self.hide = True
        elif tag == "title":
            self.in_title = True
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = tag[1]
            self.result.append(f"\n\n{'#'*int(level)} ")
        elif tag in {"p", "div", "section", "article", "tr"}:
            self.result.append("\n")
        elif tag == "li":
            self.result.append("\n- ")
        elif tag == "br":
            self.result.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "head", "noscript"}:
            self.hide = False
        elif tag == "title":
            self.in_title = False
        elif tag in {"p", "div", "tr"}:
            self.result.append("\n")

    def handle_data(self, data):
        if self.hide:
            return
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.title += text + " "
        else:
            self.result.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.result)
        lines = [ln.strip() for ln in raw.split("\n")]
        cleaned = []
        prev_empty = False
        for ln in lines:
            if not ln:
                if not prev_empty:
                    cleaned.append("")
                    prev_empty = True
            else:
                cleaned.append(ln)
                prev_empty = False
        prefix = f"# {self.title.strip()}\n\n" if self.title.strip() else ""
        return prefix + "\n".join(cleaned)

def extract_text_from_html(file_path: Path) -> str:
    encs = ["utf-8", "cp949", "euc-kr", "latin1"]
    content = None
    for enc in encs:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError(f"HTML 파일 인코딩 확인 실패: {file_path.name}")
    parser = SimpleHTMLTextExtractor()
    parser.feed(content)
    return parser.get_text()

# ---------- DOCX 텍스트 추출 ----------
def extract_text_from_docx(file_path: Path) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(file_path, "r") as z:
        if "word/document.xml" not in z.namelist():
            raise ValueError("DOCX 내부에 word/document.xml이 없습니다")
        xml_bytes = z.read("word/document.xml")
        tree = ET.fromstring(xml_bytes)
        body = tree.find("w:body", ns)
        if body is None:
            return ""
        parts = []
        for child in body:
            if child.tag.endswith('p'):
                texts = [t.text for t in child.iter(f"{{{ns['w']}}}t") if t.text]
                line = "".join(texts).strip()
                if line:
                    parts.append(line)
            elif child.tag.endswith('tbl'):
                parts.append("\n[표 데이터]")
                for row in child.iter(f"{{{ns['w']}}}tr"):
                    cells = []
                    for cell in row.iter(f"{{{ns['w']}}}tc"):
                        txt = "".join([t.text for t in cell.iter(f"{{{ns['w']}}}t") if t.text])
                        cells.append(txt.strip())
                    if cells:
                        parts.append("| " + " | ".join(cells) + " |")
        return "\n\n".join(parts)

# ---------- PPTX 텍스트 추출 ----------
def extract_text_from_pptx(file_path: Path) -> str:
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    with zipfile.ZipFile(file_path, "r") as z:
        slide_files = [n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
        slide_files.sort()
        out = []
        for idx, sfile in enumerate(slide_files, 1):
            xml_bytes = z.read(sfile)
            tree = ET.fromstring(xml_bytes)
            texts = []
            for p in tree.iter(f"{{{ns['a']}}}p"):
                seg = "".join([t.text for t in p.iter(f"{{{ns['a']}}}t") if t.text])
                if seg:
                    texts.append(seg.strip())
            if texts:
                title = texts[0]
                body = "\n- ".join(texts[1:]) if len(texts) > 1 else ""
                slide_md = f"### [슬라이드 {idx}] {title}"
                if body:
                    slide_md += f"\n- {body}"
                out.append(slide_md)
        return "\n\n".join(out)

# ---------- 일반 텍스트 추출 ----------
def extract_text_plain(file_path: Path) -> str:
    encs = ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"]
    for enc in encs:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"텍스트 파일 인코딩 확인 실패: {file_path.name}")

# ---------- 휴리스틱 요약 ----------
def heuristic_summary(text: str, filename: str) -> str:
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    # 첫 3줄을 초반 요약으로 사용 (가능하면 문단 구분)
    intro = " ".join(lines[:3]) if len(lines) >= 3 else " ".join(lines)
    # 헤딩 추출 (Markdown 스타일 혹은 ALL CAPS)
    headings = []
    for ln in lines:
        if ln.startswith('#'):
            headings.append(ln.lstrip('#').strip())
        elif ln.isupper() and len(ln.split()) <= 6:
            headings.append(ln.title())
    # Mermaid 흐름도 생성 (단순 순서)
    mermaid = """\n```mermaid\nflowchart TD\n"""
    for i, h in enumerate(headings, 1):
        node_id = f"S{i}"
        label = h.replace('"', '\\"')
        mermaid += f"    {node_id}[\"{label}\"]\n"
        if i > 1:
            mermaid += f"    S{i-1} --> {node_id}\n"
    mermaid += "```\n"

    summary_md = f"# 📄 {filename}\n\n## 1. 문서 개요\n- **파일명**: {filename}\n- **파일 형식**: {Path(filename).suffix.upper()}\n\n## 2. 핵심 요약\n{intro}\n\n## 3. 주요 섹션(헤딩)\n"
    for h in headings:
        summary_md += f"- {h}\n"
    summary_md += "\n## 4. 시각화 다이어그램\n" + mermaid
    summary_md += "\n## 5. 결론\n(자동 요약이므로 필요에 따라 수동 보완 권장)\n"
    return summary_md

# ---------- 메인 ----------
def main():
    parser = argparse.ArgumentParser(description="Offline 파일 요약기 (Gemini API 없이)")
    parser.add_argument("file", nargs="?", help="요약할 파일 경로 (생략 시 파일 선택 창 사용)")
    parser.add_argument("-o", "--output", help="결과 Markdown 파일 저장 경로")
    parser.add_argument("--no-gui", action="store_true", help="GUI 파일 선택 창 비활성화")
    args = parser.parse_args()

    # 파일 선택 로직 (GUI 없이 간단히 입력받음)
    target_path = None
    if args.file:
        target_path = Path(args.file)
    else:
        if not args.no_gui:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk(); root.withdraw()
                selected = filedialog.askopenfilename(title="요약할 파일 선택")
                root.destroy()
                if selected:
                    target_path = Path(selected)
            except Exception:
                pass
        if target_path is None:
            entered = input("요약할 파일 경로를 입력하세요 (또는 엔터로 취소): ").strip()
            if entered:
                target_path = Path(entered)
    if target_path is None or not target_path.exists():
        print("[오류] 파일을 찾을 수 없습니다.")
        sys.exit(1)

    ext = target_path.suffix.lower()
    try:
        if ext in {".html", ".htm"}:
            txt = extract_text_from_html(target_path)
        elif ext == ".docx":
            txt = extract_text_from_docx(target_path)
        elif ext == ".pptx":
            txt = extract_text_from_pptx(target_path)
        elif ext in {".txt", ".md", ".json", ".csv", ".c", ".h", ".py"}:
            txt = extract_text_plain(target_path)
        elif ext == ".pdf":
            txt = "PDF 파일은 오프라인 요약을 지원하지 않습니다. PDF를 텍스트(.txt) 로 변환 후 사용하세요."
        else:
            txt = extract_text_plain(target_path)
    except Exception as e:
        print(f"[오류] 파일 파싱 중 예외 발생: {e}")
        sys.exit(1)

    md = heuristic_summary(txt, target_path.name)

    out_path = None
    if args.output:
        out_path = Path(args.output)
        if out_path.is_dir():
            out_path = out_path / f"{target_path.stem}_summary.md"
    else:
        out_path = target_path.parent / f"{target_path.stem}_summary.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[완료] 요약 파일 생성: {out_path.resolve()}")
    print("파일을 열어 필요에 따라 내용 보강하세요.")

if __name__ == "__main__":
    main()


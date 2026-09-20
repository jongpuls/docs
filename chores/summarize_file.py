#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-format AI File Summarizer with Gemini & Mermaid
------------------------------------------------------
HTML, DOCX, PPTX, PDF, TXT, MD 등 다양한 형식의 파일을 분석하여
핵심 요약과 Mermaid 다이어그램을 포함한 Markdown(.md) 문서를 생성합니다.
"""

import os
import sys
import json
import base64
import zipfile
import argparse
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

# Optional dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# HTTP request via requests or urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# GUI file dialog via tkinter
try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog, messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SUMMARY_PROMPT = """당신은 세계 최고 수준의 테크니컬 문서 분석 및 시각화 전문가입니다.
제공된 문서(파일 내용)를 정밀하게 분석하여 읽기 쉽고 구조화된 한국어 Markdown 요약 보고서를 작성해 주세요.

## 작성 규칙 및 출력 형식:
1. **언어**: 한국어로 자연스럽고 전문적인 어조로 작성하되, 핵심 기술 용어 및 고유명사는 원어(영어)를 병기하거나 그대로 유지하세요.
2. **구조**:
   # 📄 [문서 제목 또는 핵심 주제]

   ## 1. 문서 개요 (Overview)
   - **문서명/파일**: {filename}
   - **문서 유형/포맷**: {file_type}
   - **대상 독자 및 목적**: (문서가 다루는 대상과 목적)
   - **핵심 키워드**: (3~5개 쉼표로 구분)

   ## 2. 핵심 요약 (Executive Summary)
   (문서의 가장 중요한 핵심 내용을 3~5문장으로 명확하고 간결하게 요약)

   ## 3. 상세 구조 및 주요 내용 분석 (Key Sections & Analysis)
   (문서의 각 섹션/장/슬라이드별 핵심 내용, 주요 데이터, 논리적 전개 과정을箇조조 형식으로 정리)
   - 주요 수치나 표 데이터가 있다면 마크다운 표(`| 컬럼 | ... |`)로 재구성

   ## 4. 시각화 다이어그램 (Mermaid Diagrams)
   **[중요]** 문서의 이해를 돕기 위해 문서에 포함된 프로세스, 데이터 흐름, 시스템 아키텍처, 상태 전이, 구성 요소 관계 등을 하나 이상의 Mermaid 다이어그램으로 시각화하세요.
   - **필수 준수 사항**:
     * 코드 블록은 반드시 ```mermaid 로 시작하고 ``` 로 닫으세요.
     * 지원 문법: `flowchart TD / LR`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram` 중 내용에 적합한 것 선택.
     * 괄호, 특수기호가 포함된 노드 라벨은 반드시 큰따옴표로 감싸세요 (예: `A["초기화 (Init)"] --> B["실행 (Execute)"]`).
     * 문법 오류가 없도록 간결하고 명확한 ID를 사용하세요.

   ## 5. 결론 및 주요 시사점 (Key Takeaways & Action Items)
   - **주요 결론**: (도출된 핵심 결론 2~3가지)
   - **권장 조치/적용점**: (실제 업무나 개발에 적용할 수 있는 포인트)

3. 원문의 중요한 정보가 누락되지 않도록 충실하게 요약하되, 불필요한 군더더기나 형식적인 텍스트(예: 페이지 번호, 라이선스 반복 등)는 정제하세요.
"""


class SimpleHTMLTextExtractor(HTMLParser):
    """HTML 문서를 구조화된 텍스트로 변환하는 파서"""
    def __init__(self):
        super().__init__()
        self.result = []
        self.hide_tags = {'script', 'style', 'head', 'noscript', 'meta', 'link'}
        self.current_hide_depth = 0
        self.in_title = False
        self.doc_title = ""

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in self.hide_tags:
            self.current_hide_depth += 1
        elif tag_lower == 'title':
            self.in_title = True
        elif tag_lower in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            level = tag_lower[1]
            self.result.append(f"\n\n{'#' * int(level)} ")
        elif tag_lower in {'p', 'div', 'section', 'article', 'tr'}:
            self.result.append("\n")
        elif tag_lower in {'li'}:
            self.result.append("\n- ")
        elif tag_lower in {'td', 'th'}:
            self.result.append(" | ")
        elif tag_lower == 'br':
            self.result.append("\n")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self.hide_tags:
            self.current_hide_depth = max(0, self.current_hide_depth - 1)
        elif tag_lower == 'title':
            self.in_title = False
        elif tag_lower in {'p', 'div', 'tr'}:
            self.result.append("\n")

    def handle_data(self, data):
        if self.current_hide_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.doc_title += text + " "
        else:
            self.result.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.result)
        # 빈 줄 정리
        lines = [line.strip() for line in raw.split("\n")]
        cleaned = []
        last_empty = False
        for line in lines:
            if not line:
                if not last_empty:
                    cleaned.append("")
                    last_empty = True
            else:
                cleaned.append(line)
                last_empty = False
        prefix = f"# {self.doc_title.strip()}\n\n" if self.doc_title.strip() else ""
        return prefix + "\n".join(cleaned)


def extract_text_from_docx(file_path: Path) -> str:
    """DOCX 파일에서 문단 및 표 텍스트 추출 (외부 라이브러리 없이 zipfile/xml 기반)"""
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # document.xml 읽기
            if 'word/document.xml' not in z.namelist():
                raise ValueError("DOCX 파일 내 word/document.xml이 존재하지 않습니다.")
            
            doc_xml = z.read('word/document.xml')
            tree = ET.fromstring(doc_xml)
            
            ns = {
                'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            }
            
            output_parts = []
            
            # body 내 모든 요소 순회 (문단 및 표)
            body = tree.find('w:body', ns)
            if body is None:
                return "내용이 비어있는 DOCX 문서입니다."
                
            for child in body:
                tag = child.tag
                if tag.endswith('p'):  # paragraph
                    texts = [node.text for node in child.iter(f"{{{ns['w']}}}t") if node.text]
                    line = "".join(texts).strip()
                    if line:
                        output_parts.append(line)
                elif tag.endswith('tbl'):  # table
                    output_parts.append("\n[표 데이터]")
                    for row in child.iter(f"{{{ns['w']}}}tr"):
                        row_cells = []
                        for cell in row.iter(f"{{{ns['w']}}}tc"):
                            cell_texts = [node.text for node in cell.iter(f"{{{ns['w']}}}t") if node.text]
                            row_cells.append(" ".join("".join(cell_texts).split()))
                        if row_cells:
                            output_parts.append("| " + " | ".join(row_cells) + " |")
                    output_parts.append("")
                    
            return "\n\n".join(output_parts)
    except Exception as e:
        raise RuntimeError(f"DOCX 파일 추출 실패 ({file_path.name}): {e}")


def extract_text_from_pptx(file_path: Path) -> str:
    """PPTX 파일에서 슬라이드별 제목 및 내용 추출 (외부 라이브러리 없이 zipfile/xml 기반)"""
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            names = z.namelist()
            # slide*.xml 목록 정렬
            slide_files = [n for n in names if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
            
            def slide_number(name):
                base = name.replace('ppt/slides/slide', '').replace('.xml', '')
                return int(base) if base.isdigit() else 9999
                
            slide_files.sort(key=slide_number)
            
            ns = {
                'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
            }
            
            slides_output = []
            for idx, sfile in enumerate(slide_files, start=1):
                sxml = z.read(sfile)
                tree = ET.fromstring(sxml)
                
                slide_lines = []
                # 문단별 텍스트 수집
                for p in tree.iter(f"{{{ns['a']}}}p"):
                    texts = [node.text for node in p.iter(f"{{{ns['a']}}}t") if node.text]
                    line = "".join(texts).strip()
                    if line:
                        slide_lines.append(line)
                        
                if slide_lines:
                    title = slide_lines[0]
                    body = "\n- ".join(slide_lines[1:]) if len(slide_lines) > 1 else ""
                    slide_text = f"### [슬라이드 {idx}] {title}"
                    if body:
                        slide_text += f"\n- {body}"
                    slides_output.append(slide_text)
                    
            if not slides_output:
                return "슬라이드 텍스트를 찾을 수 없습니다."
            return "\n\n".join(slides_output)
    except Exception as e:
        raise RuntimeError(f"PPTX 파일 추출 실패 ({file_path.name}): {e}")


def extract_text_from_html(file_path: Path) -> str:
    """HTML 파일에서 텍스트 추출"""
    encodings = ['utf-8', 'cp949', 'euc-kr', 'latin1']
    content = None
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
            
    if content is None:
        raise ValueError(f"HTML 파일 인코딩 인식 실패: {file_path.name}")
        
    parser = SimpleHTMLTextExtractor()
    parser.feed(content)
    return parser.get_text()


def extract_text_plain(file_path: Path) -> str:
    """텍스트/마크다운/코드 파일 읽기"""
    encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"텍스트 파일 인코딩을 해석할 수 없습니다: {file_path.name}")


def call_gemini_api(
    api_key: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    pdf_path: Optional[Path] = None
) -> str:
    """Gemini REST API 호출 (requests 또는 urllib)"""
    url = f"{GEMINI_API_ENDPOINT.format(model=model)}?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    parts = []
    
    # PDF인 경우 네이티브 멀티모달 inlineData 전송
    if pdf_path is not None:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": "application/pdf",
                "data": pdf_b64
            }
        })
    
    parts.append({"text": prompt})
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }
    
    data_json = json.dumps(payload).encode("utf-8")
    
    if HAS_REQUESTS:
        response = requests.post(url, headers=headers, data=data_json, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(
                f"Gemini API 오류 ({response.status_code}): {response.text}"
            )
        res_data = response.json()
    else:
        req = urllib.request.Request(url, data=data_json, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise RuntimeError(f"Gemini API HTTP 오류 ({e.code}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Gemini API 호출 실패: {e}")
            
    # 응답 텍스트 파싱
    try:
        candidates = res_data.get("candidates", [])
        if not candidates:
            feedback = res_data.get("promptFeedback", {})
            raise RuntimeError(f"Gemini에서 생성된 답변이 없습니다. (피드백: {feedback})")
        parts_resp = candidates[0].get("content", {}).get("parts", [])
        text_chunks = [p.get("text", "") for p in parts_resp if "text" in p]
        return "\n".join(text_chunks)
    except Exception as e:
        raise RuntimeError(f"Gemini 응답 구조 해석 실패: {e}\n원본응답: {res_data}")


def get_gemini_api_key(interactive: bool = True) -> str:
    """API 키 탐색 (환경변수 -> .env -> 프롬프트)"""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
        
    # 현재 디렉터리 및 스크립트 디렉터리의 .env 탐색
    for candidate_dir in [Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]:
        env_file = candidate_dir / ".env"
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["GEMINI_API_KEY"] = val
                                return val
            except Exception:
                pass
                
    if not interactive:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. 환경 변수 또는 .env 파일에 키를 지정해 주세요."
        )
        
    # 대화형 입력 요청 (Tkinter GUI 우선, 콘솔 대체)
    if HAS_TKINTER and sys.stdin.isatty() is False:
        try:
            root = tk.Tk()
            root.withdraw()
            user_key = simpledialog.askstring(
                "Gemini API 키 입력",
                "Google Gemini API 키가 감지되지 않았습니다.\nAPI 키를 입력해 주세요 (https://aistudio.google.com/ 에서 발급):",
                parent=root
            )
            root.destroy()
            if user_key and user_key.strip():
                # .env에 저장할지 여부
                save_env = True
                if save_env:
                    target_env = Path(__file__).resolve().parent / ".env"
                    with open(target_env, "a", encoding="utf-8") as f:
                        f.write(f"\nGEMINI_API_KEY={user_key.strip()}\n")
                    print(f"API 키가 {target_env.name}에 저장되었습니다.")
                return user_key.strip()
        except Exception:
            pass
            
    # 콘솔 입력
    print("\n[알림] GEMINI_API_KEY가 감지되지 않았습니다.")
    print("Google AI Studio (https://aistudio.google.com/)에서 발급받은 키를 입력해 주세요.")
    entered = input("Gemini API Key 입력: ").strip()
    if not entered:
        raise ValueError("API 키가 입력되지 않았습니다.")
        
    # 현재 폴더 .env에 자동 저장 지원
    target_env = Path(__file__).resolve().parent / ".env"
    try:
        with open(target_env, "a", encoding="utf-8") as f:
            f.write(f"\nGEMINI_API_KEY={entered}\n")
        print(f"-> 편의를 위해 {target_env} 파일에 키를 저장했습니다.")
    except Exception:
        pass
        
    return entered


def select_file_via_gui() -> Optional[Path]:
    """윈도우 파일 선택 대화상자 팝업"""
    if not HAS_TKINTER:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        file_types = [
            ("지원하는 모든 문서", "*.html;*.htm;*.docx;*.pptx;*.pdf;*.txt;*.md;*.json;*.csv;*.log;*.c;*.h;*.py"),
            ("HTML 문서 (*.html, *.htm)", "*.html;*.htm"),
            ("Word 문서 (*.docx)", "*.docx"),
            ("PowerPoint 슬라이드 (*.pptx)", "*.pptx"),
            ("PDF 문서 (*.pdf)", "*.pdf"),
            ("텍스트 및 마크다운 (*.txt, *.md)", "*.txt;*.md"),
            ("모든 파일 (*.*)", "*.*")
        ]
        
        selected = filedialog.askopenfilename(
            title="요약할 파일을 선택하세요",
            filetypes=file_types
        )
        root.destroy()
        return Path(selected) if selected else None
    except Exception as e:
        print(f"[경고] GUI 파일 선택 창 표시 실패: {e}")
        return None


def summarize_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL
) -> Path:
    """단일 파일을 분석하여 마크다운 요약본 생성"""
    if not input_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {input_path}")
        
    ext = input_path.suffix.lower()
    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    print(f"\n==================================================")
    print(f"📄 파일 분석 시작: {input_path.name} ({file_size_mb:.2f} MB)")
    print(f"🤖 사용할 모델: {model}")
    print(f"==================================================")
    
    if api_key is None:
        api_key = get_gemini_api_key(interactive=True)
        
    pdf_for_gemini = None
    extracted_text = ""
    file_type_desc = ext.upper()
    
    # 포맷별 내용 추출
    if ext == '.pdf':
        file_type_desc = "PDF Document"
        if file_size_mb > 20.0:
            print("[주의] 20MB를 초과하는 대용량 PDF는 API 제한에 걸릴 수 있습니다.")
        print("-> PDF 파일 분석을 위해 Gemini 멀티모달 파이프라인으로 전송 준비 중...")
        pdf_for_gemini = input_path
        user_prompt = SUMMARY_PROMPT.format(
            filename=input_path.name,
            file_type=file_type_desc
        ) + "\n\n첨부된 PDF 파일 전체의 내용을 상세히 검토하여 요약과 Mermaid 다이어그램을 작성해 주세요."
        
    elif ext in ('.docx', '.doc'):
        file_type_desc = "Word Document (.docx)"
        if ext == '.doc':
            print("[주의] 레거시 .doc 형식은 .docx로 변환 후 사용하시길 권장합니다.")
        print("-> Word(.docx) 문단 및 표(Table) 구조 추출 중...")
        extracted_text = extract_text_from_docx(input_path)
        
    elif ext in ('.pptx', '.ppt'):
        file_type_desc = "PowerPoint Presentation (.pptx)"
        if ext == '.ppt':
            print("[주의] 레거시 .ppt 형식은 .pptx로 변환 후 사용하시길 권장합니다.")
        print("-> PowerPoint(.pptx) 슬라이드별 제목 및 본문 추출 중...")
        extracted_text = extract_text_from_pptx(input_path)
        
    elif ext in ('.html', '.htm'):
        file_type_desc = "HTML Web Document"
        print("-> HTML 구조 및 본문 텍스트 추출 중...")
        extracted_text = extract_text_from_html(input_path)
        
    else:
        file_type_desc = f"Text/Source Document ({ext})"
        print(f"-> 텍스트 파일 읽기 중 ({ext})...")
        extracted_text = extract_text_plain(input_path)
        
    if pdf_for_gemini is None:
        if not extracted_text.strip():
            raise ValueError(f"파일에서 유효한 텍스트 내용을 추출하지 못했습니다: {input_path.name}")
        print(f"-> 텍스트 추출 완료 ({len(extracted_text):,} 문자)")
        user_prompt = SUMMARY_PROMPT.format(
            filename=input_path.name,
            file_type=file_type_desc
        ) + f"\n\n## 원본 파일 내용:\n```text\n{extracted_text}\n```"
        
    # Gemini API 호출
    print(f"-> Gemini AI에 문서 요약 및 Mermaid 다이어그램 생성 요청 중... (잠시만 기다려주세요)")
    summary_markdown = call_gemini_api(
        api_key=api_key,
        prompt=user_prompt,
        model=model,
        pdf_path=pdf_for_gemini
    )
    
    # 출력 경로 결정
    if output_path is None:
        out_dir = input_path.parent
        out_name = f"{input_path.stem}_summary.md"
        output_path = out_dir / out_name
    else:
        if output_path.is_dir():
            output_path = output_path / f"{input_path.stem}_summary.md"
            
    # Markdown 파일 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(summary_markdown)
        
    print(f"\n[성공] 요약 문서가 생성되었습니다!")
    print(f"📍 저장 경로: {output_path.resolve()}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Multi-format AI File Summarizer with Gemini & Mermaid")
    parser.add_argument("file", nargs="?", help="요약할 파일 경로 (생략 시 파일 선택 창이 열립니다)")
    parser.add_argument("-o", "--output", help="결과 Markdown 파일 저장 경로")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"사용할 Gemini 모델 (기본값: {DEFAULT_MODEL})")
    parser.add_argument("-k", "--key", help="Gemini API 키 (생략 시 환경 변수 또는 .env 확인)")
    parser.add_argument("--no-gui", action="store_true", help="GUI 파일 대화상자를 사용하지 않음")
    
    args = parser.parse_args()
    
    target_file = None
    if args.file:
        target_file = Path(args.file)
    else:
        if not args.no_gui and HAS_TKINTER:
            print("파일 인자가 지정되지 않아 파일 선택 창을 엽니다...")
            target_file = select_file_via_gui()
            
    if not target_file:
        print("\n파일이 지정되지 않았습니다.")
        entered = input("요약할 파일의 경로를 직접 입력해 주세요 (종료: 엔터): ").strip()
        if entered:
            target_file = Path(entered.strip('"').strip("'"))
        else:
            print("프로그램을 종료합니다.")
            sys.exit(0)
            
    out_path = Path(args.output) if args.output else None
    
    try:
        res = summarize_file(
            input_path=target_file,
            output_path=out_path,
            api_key=args.key,
            model=args.model
        )
        # 성공 메시지 안내
        print(f"\n결과 파일을 확인하려면 다음 링크를 열어보세요:")
        print(f"file:///{str(res.resolve()).replace(os.sep, '/')}")
    except Exception as e:
        print(f"\n[오류 발생] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# 🤖 AI 기반 파일 분류 & 요약기

폴더 안의 다양한 형식의 문서(HTML, Word, PowerPoint, PDF, 텍스트, 코드 등)를 **유형별로 자동 분류·복사**하고,
AI(Claude / Gemini / GPT)를 활용하여 각 파일의 **구조화된 요약 + Mermaid 다이어그램**을 포함한 Markdown 보고서를 생성합니다.

> ⚠️ **원본 파일은 절대 건드리지 않습니다** — 모든 파일은 결과 폴더로 **복사**됩니다.

---

## 📁 파일 구성

```text
d:\code\docs\chores/
├── classify_and_summarize.py   # 핵심 엔진: 분류 + 텍스트 추출 + manifest 생성
├── run_summarizer.bat          # 윈도우 GUI 실행기 (더블 클릭)
├── offline_summarizer.py       # 단일 파일 오프라인 요약 (API 없이)
├── summarize_file.py           # 단일 파일 Gemini API 요약 (API 키 필요)
├── README.md                   # 본 안내 문서
└── test_samples/               # 테스트용 샘플 파일
```

---

## 🚀 사용 방법

### 방법 1: Antigravity 채팅창 (가장 추천)

채팅창에서 파일 요약/분류를 요청하면 에이전트가 3가지를 물어봅니다:
1. **원본 폴더 경로** — 분류할 파일이 있는 폴더
2. **결과 저장 경로** — 분류된 파일과 요약이 저장될 폴더
3. **사용할 AI** — Claude / Gemini / GPT 중 선택

에이전트가 스크립트를 실행하여 파일을 분류하고, 선택한 AI 모델로 각 파일을 요약합니다.

#### 예시 요청:
- *"chores/test_samples 폴더의 파일들을 분류하고 요약해 줘"*
- *"D:\documents 폴더 파일들을 정리하고 각각 요약 마크다운 만들어 줘"*

---

### 방법 2: 배치 파일 더블 클릭 (GUI)

1. `run_summarizer.bat`을 **더블 클릭**합니다.
2. 안내에 따라 원본 폴더, 결과 폴더, AI 선택을 입력합니다.
3. 파일 분류·복사 및 텍스트 추출이 자동으로 수행됩니다.

---

### 방법 3: CLI 직접 실행

```powershell
python d:\code\docs\chores\classify_and_summarize.py "<원본폴더>" "<결과폴더>" --ai <claude|gemini|gpt>
```

예시:
```powershell
python d:\code\docs\chores\classify_and_summarize.py "D:\documents" "D:\output\classified" --ai claude
```

---

## 📂 결과 폴더 구조 예시

```text
D:\output\classified/
├── _manifest.json              # 전체 파일 목록 + 추출 텍스트 (에이전트용)
├── _classification_report.md   # 분류 리포트 (카테고리별 현황 + Mermaid)
├── documents/                  # 📄 문서 (DOCX, PDF, TXT)
│   ├── report.docx
│   └── report_summary.md       # ← AI 요약 결과
├── presentations/              # 📊 프레젠테이션 (PPTX)
│   ├── slides.pptx
│   └── slides_summary.md
├── web/                        # 🌐 웹 문서 (HTML)
│   ├── page.html
│   └── page_summary.md
├── code/                       # 💻 소스코드
│   └── main.py
├── markup/                     # 📝 마크업/설정
│   └── config.json
└── images/                     # 🖼️ 이미지
    └── diagram.png
```

---

## 📊 분류 카테고리

| 카테고리 | 확장자 | 아이콘 |
|----------|--------|--------|
| documents | `.docx`, `.doc`, `.pdf`, `.txt`, `.rtf` | 📄 |
| presentations | `.pptx`, `.ppt`, `.odp` | 📊 |
| spreadsheets | `.xlsx`, `.xls`, `.csv` | 📈 |
| web | `.html`, `.htm`, `.xhtml` | 🌐 |
| markup | `.md`, `.json`, `.xml`, `.yaml`, `.toml` | 📝 |
| code | `.py`, `.c`, `.h`, `.java`, `.js`, `.ts` 등 | 💻 |
| images | `.png`, `.jpg`, `.gif`, `.svg` 등 | 🖼️ |
| archives | `.zip`, `.tar`, `.gz`, `.7z` | 📦 |
| others | 위에 해당하지 않는 파일 | 📁 |

---

## 📝 요약 문서 형식

각 파일의 `_summary.md`는 다음 구조로 작성됩니다:

1. **문서 개요** — 파일명, 포맷, 카테고리, 핵심 키워드
2. **핵심 요약** — 3~5문장 요약
3. **상세 분석** — 섹션별 핵심 내용
4. **Mermaid 다이어그램** — 흐름도, 시퀀스, 상태도 등
5. **결론 및 시사점** — 주요 결론 및 권장 조치

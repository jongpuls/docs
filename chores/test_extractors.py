import sys
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import summarize_file

test_dir = Path(__file__).resolve().parent / "test_samples"
test_dir.mkdir(parents=True, exist_ok=True)

# 1. HTML sample
html_content = """<!DOCTYPE html>
<html>
<head><title>시스템 아키텍처 개요</title></head>
<body>
  <h1>클라우드 마이크로서비스 설계서</h1>
  <p>본 문서는 사용자 인증 및 결제 시스템의 마이크로서비스 구조를 정의합니다.</p>
  <h2>핵심 모듈</h2>
  <ul>
    <li>Auth Service: JWT 기반 사용자 인증</li>
    <li>Order Service: 주문 생성 및 결제 연동</li>
    <li>Notification Service: 알림 발송</li>
  </ul>
  <h2>서비스 지표</h2>
  <table>
    <tr><th>서비스</th><th>목표 응답시간</th></tr>
    <tr><td>Auth</td><td>50ms</td></tr>
    <tr><td>Order</td><td>100ms</td></tr>
  </table>
</body>
</html>"""

html_file = test_dir / "sample.html"
with open(html_file, "w", encoding="utf-8") as f:
    f.write(html_content)

extracted_html = summarize_file.extract_text_from_html(html_file)
print("--- HTML Extracted ---")
print(extracted_html)

# 2. DOCX sample (minimal valid docx with word/document.xml)
docx_file = test_dir / "sample.docx"
doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>EDK2 부팅 프로세스 명세서</w:t></w:r></w:p>
    <w:p><w:r><w:t>SEC -> PEI -> DXE -> BDS 로 이어지는 부팅 단계 분석.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>단계</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>역할</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>SEC</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>보안 및 초기화</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""

with zipfile.ZipFile(docx_file, "w") as z:
    z.writestr("word/document.xml", doc_xml)

extracted_docx = summarize_file.extract_text_from_docx(docx_file)
print("\n--- DOCX Extracted ---")
print(extracted_docx)

# 3. PPTX sample (minimal valid pptx with ppt/slides/slide1.xml)
pptx_file = test_dir / "sample.pptx"
slide1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>차세대 펌웨어 아키텍처 발표</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>주요 발표 내용:</a:t></a:r></a:p>
          <a:p><a:r><a:t>1. Rust 기반 UEFI 드라이버 도입</a:t></a:r></a:p>
          <a:p><a:r><a:t>2. 보안 부팅(Secure Boot) 성능 30% 개선</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

with zipfile.ZipFile(pptx_file, "w") as z:
    z.writestr("ppt/slides/slide1.xml", slide1_xml)

extracted_pptx = summarize_file.extract_text_from_pptx(pptx_file)
print("\n--- PPTX Extracted ---")
print(extracted_pptx)

print("\nAll extractors tested successfully!")

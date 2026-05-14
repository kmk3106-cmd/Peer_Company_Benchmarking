"""종합 보고서용 QR 코드 + 다운로드 페이지 생성.

URL: GitHub raw + HTML preview (htmlpreview.github.io) 2개 제공.
"""
from __future__ import annotations
import qrcode
from pathlib import Path

# GitHub URLs
REPO = "kmk3106-cmd/Peer_Company_Benchmarking"
BRANCH = "main"
FILE = "report/종합보고서_FY2025.html"

# Raw URL (다운로드)
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{FILE}"
# htmlpreview proxy (브라우저에서 바로 렌더링)
PREVIEW_URL = f"https://htmlpreview.github.io/?{RAW_URL}"

print(f"📥 다운로드 URL (raw):\n   {RAW_URL}\n")
print(f"🌐 브라우저 미리보기 URL:\n   {PREVIEW_URL}\n")

# QR 코드 생성 — preview URL이 태블릿 친화적
out_dir = Path("report")
qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
qr.add_data(PREVIEW_URL)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
qr_path = out_dir / "qr_종합보고서.png"
img.save(qr_path)
print(f"✓ QR 코드 (preview): {qr_path}")

# raw URL용 QR (다운로드 직링크)
qr2 = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
qr2.add_data(RAW_URL)
qr2.make(fit=True)
img2 = qr2.make_image(fill_color="black", back_color="white")
qr2_path = out_dir / "qr_종합보고서_raw.png"
img2.save(qr2_path)
print(f"✓ QR 코드 (raw download): {qr2_path}")

# 다운로드 안내 HTML 페이지
landing_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>종합 보고서 다운로드</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
    max-width: 600px; margin: 0 auto; padding: 24px;
    color: #222; background: #f5f7fa;
  }}
  h1 {{ font-size: clamp(20pt, 5vw, 28pt); color: #1a3870; }}
  .card {{ background: #fff; border-radius: 12px; padding: 20px; margin: 16px 0;
          box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
  .card h2 {{ margin-top: 0; font-size: clamp(14pt, 3.5vw, 18pt); color: #1a3870; }}
  .btn {{ display: inline-block; background: #4a76d8; color: white;
         padding: 14px 24px; border-radius: 8px; text-decoration: none;
         font-size: clamp(11pt, 2.8vw, 14pt); font-weight: 600;
         margin: 8px 4px; }}
  .btn:hover {{ background: #1a3870; }}
  .btn.secondary {{ background: #5a6a85; }}
  .url {{ font-family: monospace; font-size: clamp(9pt, 2vw, 11pt);
        background: #eef; padding: 8px 10px; border-radius: 6px;
        word-break: break-all; margin: 8px 0; }}
  p, li {{ font-size: clamp(10pt, 2.5vw, 12pt); line-height: 1.6; }}
</style>
</head>
<body>

<h1>📊 동업사 비교검증 보고서</h1>
<p>FY2025 · 미래에셋생명 계리결산팀</p>

<div class="card">
  <h2>🌐 바로 보기 (브라우저)</h2>
  <p>태블릿·PC에서 바로 열어볼 수 있습니다.</p>
  <a href="{PREVIEW_URL}" class="btn">보고서 열기</a>
  <div class="url">{PREVIEW_URL}</div>
</div>

<div class="card">
  <h2>📥 파일 다운로드</h2>
  <p>HTML 파일을 직접 받아 오프라인 보관할 수 있습니다.</p>
  <a href="{RAW_URL}" class="btn secondary" download>HTML 다운로드</a>
  <div class="url">{RAW_URL}</div>
</div>

<div class="card">
  <h2>📂 GitHub 저장소</h2>
  <p>전체 소스 코드와 산출 데이터:</p>
  <a href="https://github.com/{REPO}" class="btn secondary">GitHub 열기</a>
</div>

</body>
</html>
"""
(out_dir / "다운로드.html").write_text(landing_html, encoding="utf-8")
print(f"✓ 다운로드 안내 페이지: {out_dir / '다운로드.html'}")

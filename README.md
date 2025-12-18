# 🖼️ 한글 인포그래픽 교정 도구 v2.0

AI 생성 인포그래픽의 깨진 한글 텍스트를 교정하는 Streamlit 웹앱입니다.

## ✨ 주요 기능

- **캔버스 드래그 선택**: 마우스로 수정할 영역만 직접 선택
- **OCR 텍스트 추출**: 선택 영역에서 자동으로 텍스트 인식
- **장평(가로폭) 조절**: 텍스트 가로 비율 조정 가능
- **폰트/크기/색상 설정**: 자유로운 스타일 커스터마이징
- **PNG 내보내기**: 교정된 이미지 다운로드

## 🚀 Streamlit Cloud 배포

### 1. GitHub 저장소 생성

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/korean-infographic-fixer.git
git push -u origin main
```

### 2. Streamlit Cloud 연동

1. https://streamlit.io/cloud 접속
2. GitHub 계정으로 로그인
3. "New app" → 저장소 선택
4. Main file: `app.py`
5. Deploy!

## 📁 프로젝트 구조

```
korean-infographic-fixer-v2/
├── app.py                # 메인 Streamlit 앱
├── requirements.txt      # Python 의존성
├── packages.txt          # 시스템 패키지 (Tesseract)
├── modules/
│   ├── __init__.py
│   ├── ocr_engine.py     # OCR 및 텍스트 추출
│   ├── text_renderer.py  # 텍스트 렌더링 (장평 지원)
│   ├── inpainter.py      # 배경 복원
│   ├── style_classifier.py
│   ├── exporter.py
│   └── metadata_builder.py
└── fonts/                # 한글 폰트 파일 (.ttf)
```

## 🔧 폰트 추가

`fonts/` 폴더에 한글 폰트 파일(.ttf)을 추가하세요:

- [Noto Sans KR](https://fonts.google.com/noto/specimen/Noto+Sans+KR)
- [나눔스퀘어](https://hangeul.naver.com/font)

**예시:**
```
fonts/
├── NotoSansKR-Regular.ttf
├── NotoSansKR-Bold.ttf
└── NanumSquareB.ttf
```

## 📖 사용 방법

1. **Step 1**: 교정할 인포그래픽 이미지 업로드
2. **Step 2**: 캔버스에서 수정할 텍스트 영역을 마우스로 드래그
3. **Step 3**: OCR 결과 확인 후 텍스트/폰트/크기/색상 수정
4. **Step 4**: 완성된 이미지 다운로드

## ⚠️ 주의사항

- Streamlit Cloud 무료 플랜은 Public 저장소만 지원
- 큰 이미지는 처리 시간이 길어질 수 있음
- 폰트 파일은 저장소에 직접 포함해야 함

## 📝 라이선스

MIT License

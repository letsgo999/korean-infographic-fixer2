"""
Korean Infographic Fixer - Streamlit Main App
v2.0 - 캔버스 드래그로 텍스트 영역 선택
"""
import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import os
import uuid
import base64
from datetime import datetime

# ==============================================================================
# [필수 호환성 패치] 
# Streamlit 1.52+ 버전에서 삭제된 'image_to_url' 기능을 수동으로 복구합니다.
# 주의: 이 코드는 반드시 'streamlit_drawable_canvas' 임포트보다 위에 있어야 합니다.
# ==============================================================================
import streamlit.elements.image

def local_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None):
    """
    Streamlit 내부 함수 image_to_url을 대체하여,
    이미지를 Base64 URL로 변환해주는 함수입니다.
    """
    if output_format.upper() == "JPEG" and image.mode == "RGBA":
        image = image.convert("RGB")
        
    with io.BytesIO() as buffer:
        image.save(buffer, format=output_format)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        
    return f"data:image/{output_format.lower()};base64,{encoded}"

if not hasattr(streamlit.elements.image, 'image_to_url'):
    streamlit.elements.image.image_to_url = local_image_to_url
# ==============================================================================

# [중요] 패치가 완료된 후에 라이브러리를 임포트해야 합니다.
from streamlit_drawable_canvas import st_canvas

# Modules
from modules import (
    TextRegion,
    extract_text_from_crop,
    apply_styles_and_colors,
    CompositeRenderer,
    MultiFormatExporter,
    MetadataBuilder,
    create_inpainter
)

# 페이지 설정
st.set_page_config(
    layout="wide", 
    page_title="한글 인포그래픽 교정 도구",
    page_icon="🖼️"
)

# ==============================================================================
# 세션 상태 초기화
# ==============================================================================
def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'current_step': 1,
        'original_image': None,
        'uploaded_filename': None,
        'text_regions': [],
        'edited_texts': {},
        'canvas_key': "canvas_v1",
        'scroll_y': 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==============================================================================
# 유틸리티 함수
# ==============================================================================
def draw_regions_on_image(image, regions, edited_texts):
    """텍스트 영역을 이미지에 표시"""
    vis_image = image.copy()
    
    for region in regions:
        if isinstance(region, dict):
            r_id = region['id']
            bounds = region['bounds']
            text = region['text']
            is_inverted = region.get('is_inverted', False)
        else:
            r_id = region.id
            bounds = region.bounds
            text = region.text
            is_inverted = region.is_inverted
        
        x, y, w, h = bounds['x'], bounds['y'], bounds['width'], bounds['height']
        
        # 색상 결정
        if r_id in edited_texts and edited_texts[r_id] != text:
            color = (255, 0, 255)  # 마젠타: 수정됨
            thickness = 3
        elif is_inverted:
            color = (255, 100, 0)  # 주황: 역상
            thickness = 2
        else:
            color = (0, 255, 0)    # 녹색: 일반
            thickness = 2
        
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, thickness)
        
        # 영역 번호 표시
        cv2.putText(vis_image, r_id.split('_')[-1], (x+2, y+15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    return vis_image

def get_available_fonts():
    """사용 가능한 폰트 목록 반환"""
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir)
    
    fonts = sorted([f for f in os.listdir(fonts_dir) if f.lower().endswith(('.ttf', '.otf'))])
    
    if not fonts:
        fonts = ["Default (시스템 폰트)"]
    
    return fonts, fonts_dir

# ==============================================================================
# Step 1: 이미지 업로드
# ==============================================================================
def render_step1_upload():
    """Step 1: 이미지 업로드"""
    st.header("📤 Step 1: 이미지 업로드")
    
    st.info("""
    **사용 방법:**
    1. 교정할 인포그래픽 이미지를 업로드합니다.
    2. 다음 단계에서 마우스로 수정할 텍스트 영역을 드래그하여 선택합니다.
    3. 선택한 영역의 텍스트를 수정하고 폰트/크기/색상을 조정합니다.
    4. 최종 결과물을 다운로드합니다.
    """)
    
    uploaded_file = st.file_uploader(
        "인포그래픽 이미지를 업로드하세요",
        type=['png', 'jpg', 'jpeg', 'webp'],
        help="PNG, JPG, JPEG, WEBP 형식 지원"
    )
    
    if uploaded_file is not None:
        # 이미지 로드
        image_bytes = uploaded_file.read()
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        # 세션에 저장
        st.session_state.original_image = image
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.scroll_y = 0
        st.session_state.text_regions = []
        st.session_state.edited_texts = {}
        
        # 이미지 표시
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(
                cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
                caption=f"업로드된 이미지: {uploaded_file.name}",
                use_container_width=True
            )
        with col2:
            st.success("✅ 이미지 업로드 완료!")
            st.info(f"""
            **이미지 정보**
            - 파일명: {uploaded_file.name}
            - 크기: {image.shape[1]} x {image.shape[0]} px
            """)
        
        if st.button("🎯 텍스트 영역 선택하기 →", type="primary", use_container_width=True):
            st.session_state.current_step = 2
            st.session_state.canvas_key = f"canvas_{uuid.uuid4().hex[:8]}"
            st.rerun()

# ==============================================================================
# Step 2: 텍스트 영역 선택 (캔버스)
# ==============================================================================
def render_step2_detect():
    """Step 2: 캔버스에서 텍스트 영역 드래그 선택"""
    st.header("🎯 Step 2: 텍스트 영역 선택")
    
    if st.session_state.original_image is None:
        st.warning("⚠️ 먼저 이미지를 업로드해주세요.")
        if st.button("← Step 1로 돌아가기"):
            st.session_state.current_step = 1
            st.rerun()
        return

    original_image = st.session_state.original_image
    h_orig, w_orig = original_image.shape[:2]
    
    # 캔버스 설정
    CANVAS_WIDTH = 700
    VIEWPORT_HEIGHT = 800
    
    # 스케일 계산
    if w_orig > CANVAS_WIDTH:
        scale_factor = w_orig / CANVAS_WIDTH
    else:
        scale_factor = 1.0
        CANVAS_WIDTH = w_orig

    # 스크롤 (이미지가 길 경우)
    current_scroll = st.session_state.scroll_y
    if h_orig > VIEWPORT_HEIGHT:
        st.info("💡 이미지가 세로로 길어서 부분적으로 표시됩니다. 슬라이더로 작업 위치를 이동하세요.")
        max_scroll = h_orig - VIEWPORT_HEIGHT
        current_scroll = st.slider(
            "↕️ 작업 위치 이동",
            0, max_scroll,
            st.session_state.scroll_y,
            step=50,
            help="이미지의 다른 부분을 작업하려면 슬라이더를 움직이세요"
        )
        st.session_state.scroll_y = current_scroll
    
    # 현재 보이는 영역 자르기
    crop_h = min(VIEWPORT_HEIGHT, h_orig - current_scroll)
    crop_img = original_image[current_scroll:current_scroll + crop_h, :]
    
    # 리사이징
    h_crop, w_crop = crop_img.shape[:2]
    disp_w = int(w_crop / scale_factor)
    disp_h = int(h_crop / scale_factor)
    display_img = cv2.resize(crop_img, (disp_w, disp_h), interpolation=cv2.INTER_AREA)

    # RGB 변환 및 PIL 이미지
    img_rgb = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(img_rgb)

    # UI
    st.caption(f"📍 현재 작업 위치: Y={current_scroll}px ~ {current_scroll + crop_h}px (전체 높이: {h_orig}px)")
    
    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
        if st.button("🔄 캔버스 초기화"):
            st.session_state.canvas_key = f"canvas_{uuid.uuid4().hex[:8]}"
            st.rerun()
    with col_btn2:
        if st.button("← 이전 단계"):
            st.session_state.current_step = 1
            st.rerun()

    st.markdown("**🖱️ 마우스로 드래그하여 수정할 텍스트 영역을 선택하세요:**")
    
    # 캔버스
    try:
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.15)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=pil_image,
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode="rect",
            key=st.session_state.canvas_key,
            display_toolbar=True
        )
    except Exception as e:
        st.error(f"❌ 캔버스 로드 실패: {e}")
        st.info("페이지를 새로고침하거나 다시 시도해주세요.")
        return

    # 선택된 영역 처리
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])
        
        if len(objects) > 0:
            st.success(f"✅ 선택된 영역: **{len(objects)}개**")
            
            # 미리보기 테이블
            with st.expander("📋 선택된 영역 목록 보기", expanded=False):
                for i, obj in enumerate(objects):
                    x_real = int(obj["left"] * scale_factor)
                    y_real = int(obj["top"] * scale_factor + current_scroll)
                    w_real = int(obj["width"] * scale_factor)
                    h_real = int(obj["height"] * scale_factor)
                    st.text(f"영역 {i+1}: X={x_real}, Y={y_real}, W={w_real}, H={h_real}")
            
            if st.button("📝 텍스트 추출 및 편집하기 →", type="primary", use_container_width=True):
                with st.spinner("🔄 텍스트 추출 중..."):
                    regions = []
                    
                    for i, obj in enumerate(objects):
                        # 좌표 변환 (캔버스 -> 원본 이미지)
                        x_view = obj["left"] * scale_factor
                        y_view = obj["top"] * scale_factor
                        w_view = obj["width"] * scale_factor
                        h_view = obj["height"] * scale_factor
                        
                        x_real = int(x_view)
                        y_real = int(y_view + current_scroll)
                        w_real = int(w_view)
                        h_real = int(h_view)
                        
                        # 경계 검사
                        x_real = max(0, min(x_real, w_orig - 1))
                        y_real = max(0, min(y_real, h_orig - 1))
                        w_real = max(10, min(w_real, w_orig - x_real))
                        h_real = max(10, min(h_real, h_orig - y_real))
                        
                        if w_real < 5 or h_real < 5:
                            continue
                        
                        # OCR로 텍스트 추출
                        region = extract_text_from_crop(
                            original_image, 
                            x_real, y_real, 
                            w_real, h_real
                        )
                        
                        region.id = f"region_{i:03d}"
                        region.suggested_font_size = max(12, min(int(h_real * 0.7), 72))
                        region.width_scale = 100
                        region.font_filename = "NotoSansKR-Regular.ttf"
                        
                        regions.append(region.to_dict())
                    
                    if regions:
                        st.session_state.text_regions = regions
                        st.session_state.current_step = 3
                        st.rerun()
                    else:
                        st.error("선택된 영역이 너무 작습니다. 더 크게 선택해주세요.")
        else:
            st.info("👆 마우스로 드래그하여 텍스트 영역을 선택하세요.")

# ==============================================================================
# Step 3: 텍스트 편집
# ==============================================================================
def render_step3_edit():
    """Step 3: 텍스트 편집"""
    st.header("✏️ Step 3: 텍스트 편집")
    
    if not st.session_state.text_regions:
        st.warning("⚠️ 선택된 텍스트 영역이 없습니다.")
        if st.button("← Step 2로 돌아가기"):
            st.session_state.current_step = 2
            st.rerun()
        return
    
    image = st.session_state.original_image
    regions = st.session_state.text_regions
    
    # 폰트 목록 가져오기
    available_fonts, fonts_dir = get_available_fonts()
    
    col1, col2 = st.columns([1, 1])
    
    # 좌측: 편집 폼
    with col1:
        st.subheader(f"📝 텍스트 영역 ({len(regions)}개)")
        
        for i, region in enumerate(regions):
            region_id = region['id']
            original_text = region['text']
            
            # 제목 (텍스트 미리보기)
            display_text = original_text[:25] + "..." if len(original_text) > 25 else original_text
            if not display_text.strip():
                display_text = "(텍스트 없음)"
            
            with st.expander(f"**{i+1}.** {display_text}", expanded=(i < 3)):
                # OCR 결과 표시
                if region.get('confidence', 0) > 0:
                    st.caption(f"🔍 OCR 인식 결과 (신뢰도: {region.get('confidence', 0):.0f}%)")
                
                # 텍스트 입력
                current_text = st.session_state.edited_texts.get(region_id, original_text)
                edited_text = st.text_area(
                    "텍스트 내용",
                    value=current_text,
                    key=f"text_{region_id}",
                    height=80,
                    help="수정할 텍스트를 입력하세요"
                )
                
                # 스타일 설정
                col_a, col_b = st.columns(2)
                with col_a:
                    # 폰트 선택
                    current_font = region.get('font_filename', available_fonts[0] if available_fonts else "Default")
                    try:
                        font_idx = available_fonts.index(current_font)
                    except ValueError:
                        font_idx = 0
                    
                    selected_font = st.selectbox(
                        "폰트",
                        available_fonts,
                        index=font_idx,
                        key=f"font_{region_id}"
                    )
                    
                    # 폰트 크기
                    font_size = st.number_input(
                        "크기 (px)",
                        min_value=8,
                        max_value=120,
                        value=int(region.get('suggested_font_size', 16)),
                        key=f"size_{region_id}"
                    )
                
                with col_b:
                    # 장평
                    width_scale = st.number_input(
                        "장평 (%)",
                        min_value=50,
                        max_value=150,
                        value=int(region.get('width_scale', 100)),
                        key=f"scale_{region_id}",
                        help="100=기본, 90=좁게, 110=넓게"
                    )
                    
                    # 색상
                    text_color = st.color_picker(
                        "글자색",
                        value=region.get('text_color', '#000000'),
                        key=f"color_{region_id}"
                    )
                
                # 적용 버튼
                if st.button("💾 저장", key=f"save_{region_id}", use_container_width=True):
                    st.session_state.edited_texts[region_id] = edited_text
                    
                    # 영역 정보 업데이트
                    for r in st.session_state.text_regions:
                        if r['id'] == region_id:
                            r['text'] = edited_text
                            r['suggested_font_size'] = font_size
                            r['width_scale'] = width_scale
                            r['text_color'] = text_color
                            r['font_filename'] = selected_font
                            break
                    
                    st.success("✅ 저장됨!")
                    st.rerun()
    
    # 우측: 미리보기
    with col2:
        st.subheader("🖼️ 미리보기")
        
        visualized = draw_regions_on_image(image, regions, st.session_state.edited_texts)
        st.image(
            cv2.cvtColor(visualized, cv2.COLOR_BGR2RGB),
            caption="🟢 일반 | 🟣 수정됨",
            use_container_width=True
        )
        
        # 범례
        st.caption("""
        **색상 범례:**
        - 🟢 녹색: 원본 상태
        - 🟣 마젠타: 텍스트 수정됨
        """)
    
    st.divider()
    
    # 네비게이션
    col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 1])
    with col_nav1:
        if st.button("← 영역 다시 선택", use_container_width=True):
            st.session_state.current_step = 2
            st.session_state.canvas_key = f"canvas_{uuid.uuid4().hex[:8]}"
            st.rerun()
    with col_nav3:
        if st.button("📤 결과물 생성하기 →", type="primary", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()

# ==============================================================================
# Step 4: 결과물 생성 및 내보내기
# ==============================================================================
def render_step4_export():
    """Step 4: 결과물 생성 및 내보내기"""
    st.header("📤 Step 4: 결과물 생성")
    
    if not st.session_state.text_regions:
        st.warning("⚠️ 편집된 텍스트 영역이 없습니다.")
        return
    
    image = st.session_state.original_image
    regions = st.session_state.text_regions
    
    # TextRegion 객체로 변환
    target_objects = []
    for r in regions:
        region_text = st.session_state.edited_texts.get(r['id'], r['text'])
        
        obj = TextRegion(
            id=r['id'],
            text=region_text,
            confidence=r.get('confidence', 100),
            bounds=r['bounds'],
            is_inverted=r.get('is_inverted', False),
            is_manual=True,
            suggested_font_size=r.get('suggested_font_size', 16),
            text_color=r.get('text_color', '#000000'),
            bg_color=r.get('bg_color', '#FFFFFF'),
            font_filename=r.get('font_filename', 'NotoSansKR-Regular.ttf'),
            width_scale=r.get('width_scale', 100)
        )
        target_objects.append(obj)
    
    try:
        with st.spinner("🔄 이미지 생성 중..."):
            # 1. 텍스트 영역 제거 (배경 생성)
            inpainter = create_inpainter("simple_fill")
            background = inpainter.remove_all_text_regions(image, target_objects)
            
            # 2. 새 텍스트 합성
            fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
            renderer = CompositeRenderer(fonts_dir)
            final_image = renderer.composite(
                background,
                target_objects,
                st.session_state.edited_texts
            )
        
        st.success("✅ 이미지 생성 완료!")
        
        # 결과 표시
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("원본")
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), use_container_width=True)
        
        with col2:
            st.subheader("결과물")
            st.image(cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB), use_container_width=True)
        
        st.divider()
        
        # 다운로드 버튼
        col_dl1, col_dl2 = st.columns(2)
        
        with col_dl1:
            # PNG 다운로드
            is_success, buffer = cv2.imencode(".png", final_image)
            if is_success:
                filename = f"fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                st.download_button(
                    "📥 PNG 다운로드",
                    data=buffer.tobytes(),
                    file_name=filename,
                    mime="image/png",
                    use_container_width=True
                )
        
        with col_dl2:
            # 메타데이터 다운로드
            builder = MetadataBuilder()
            builder.set_image_info(
                filename=st.session_state.uploaded_filename or "image.png",
                width=image.shape[1],
                height=image.shape[0]
            )
            builder.set_regions(regions)
            metadata_json = builder.to_json()
            
            st.download_button(
                "📥 메타데이터 (JSON)",
                data=metadata_json,
                file_name=f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        import traceback
        st.code(traceback.format_exc())
    
    st.divider()
    
    # 네비게이션
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← 텍스트 수정하기", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    with col_nav2:
        if st.button("🔄 처음부터 다시", use_container_width=True):
            st.session_state.current_step = 1
            st.session_state.original_image = None
            st.session_state.text_regions = []
            st.session_state.edited_texts = {}
            st.rerun()

# ==============================================================================
# 사이드바
# ==============================================================================
def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("🖼️ 한글 인포그래픽 교정 도구")
        st.caption("v2.0 - 캔버스 드래그 선택")
        
        st.divider()
        
        # 진행 상태
        st.subheader("📍 진행 상태")
        steps = ["1. 업로드", "2. 영역 선택", "3. 텍스트 편집", "4. 내보내기"]
        current = st.session_state.current_step
        
        for i, step in enumerate(steps, 1):
            if i < current:
                st.markdown(f"✅ ~~{step}~~")
            elif i == current:
                st.markdown(f"**🔵 {step}**")
            else:
                st.markdown(f"⚪ {step}")
        
        st.divider()
        
        # 현재 상태
        if st.session_state.original_image is not None:
            st.subheader("📊 현재 상태")
            st.metric("텍스트 영역", len(st.session_state.text_regions))
            st.metric("수정된 영역", len(st.session_state.edited_texts))
        
        st.divider()
        
        # 도움말
        with st.expander("❓ 도움말"):
            st.markdown("""
            **사용 방법:**
            1. PNG/JPG 이미지 업로드
            2. 캔버스에서 수정할 영역 드래그
            3. OCR 결과 확인 후 텍스트 수정
            4. 결과물 다운로드
            
            **폰트 추가:**
            `fonts/` 폴더에 .ttf 파일 추가
            
            **문의:**
            GitHub Issues 활용
            """)

# ==============================================================================
# 메인
# ==============================================================================
def main():
    init_session_state()
    render_sidebar()
    
    # 현재 단계에 따라 렌더링
    step = st.session_state.current_step
    
    if step == 1:
        render_step1_upload()
    elif step == 2:
        render_step2_detect()
    elif step == 3:
        render_step3_edit()
    elif step == 4:
        render_step4_export()

if __name__ == "__main__":
    main()

"""
Korean Infographic Fixer - Streamlit Main App
v2.2 - 캔버스 없이 좌표 입력 방식 (호환성 최대화)
"""
import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import os
import uuid
from datetime import datetime

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
        'pending_regions': [],  # 추가 대기 중인 영역들
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==============================================================================
# 유틸리티 함수
# ==============================================================================
def draw_regions_on_image(image, regions, edited_texts=None, pending_regions=None):
    """텍스트 영역을 이미지에 표시"""
    vis_image = image.copy()
    edited_texts = edited_texts or {}
    pending_regions = pending_regions or []
    
    # 기존 확정된 영역 (녹색)
    for i, region in enumerate(regions):
        if isinstance(region, dict):
            bounds = region['bounds']
            text = region['text']
        else:
            bounds = region.bounds
            text = region.text
        
        x, y, w, h = bounds['x'], bounds['y'], bounds['width'], bounds['height']
        color = (0, 255, 0)  # 녹색
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
        
        # 번호 표시
        label = f"{i+1}"
        cv2.putText(vis_image, label, (x+5, y+20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    # 대기 중인 영역 (빨간색)
    for i, region in enumerate(pending_regions):
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        color = (0, 0, 255)  # 빨간색 (BGR)
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
        
        # 번호 표시
        label = f"NEW{i+1}"
        cv2.putText(vis_image, label, (x+5, y+20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
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
    2. 다음 단계에서 수정할 텍스트 영역의 좌표를 입력합니다.
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
        st.session_state.text_regions = []
        st.session_state.edited_texts = {}
        st.session_state.pending_regions = []
        
        # 이미지 표시
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(
                cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
                caption=f"업로드된 이미지: {uploaded_file.name}",
                use_column_width=True
            )
        with col2:
            st.success("✅ 이미지 업로드 완료!")
            st.info(f"""
            **이미지 정보**
            - 파일명: {uploaded_file.name}
            - 크기: {image.shape[1]} x {image.shape[0]} px
            """)
        
        if st.button("🎯 텍스트 영역 선택하기 →", type="primary"):
            st.session_state.current_step = 2
            st.rerun()

# ==============================================================================
# Step 2: 텍스트 영역 선택 (좌표 입력 방식)
# ==============================================================================
def render_step2_detect():
    """Step 2: 좌표 입력으로 텍스트 영역 선택"""
    st.header("🎯 Step 2: 텍스트 영역 선택")
    
    if st.session_state.original_image is None:
        st.warning("⚠️ 먼저 이미지를 업로드해주세요.")
        if st.button("← Step 1로 돌아가기"):
            st.session_state.current_step = 1
            st.rerun()
        return

    original_image = st.session_state.original_image
    h_orig, w_orig = original_image.shape[:2]
    
    # 레이아웃: 좌측 이미지, 우측 입력폼
    col_img, col_form = st.columns([2, 1])
    
    with col_img:
        st.subheader("📍 원본 이미지")
        st.caption(f"이미지 크기: {w_orig} x {h_orig} px")
        
        # 영역이 표시된 이미지
        visualized = draw_regions_on_image(
            original_image, 
            st.session_state.text_regions,
            pending_regions=st.session_state.pending_regions
        )
        st.image(
            cv2.cvtColor(visualized, cv2.COLOR_BGR2RGB),
            caption="🟢 확정된 영역 | 🔴 추가 대기 영역",
            use_column_width=True
        )
        
        st.info("""
        💡 **좌표 확인 방법:**
        1. 이미지를 다운로드하거나 그림판에서 열기
        2. 수정할 텍스트 영역의 좌측 상단 좌표(X, Y)와 크기(W, H) 확인
        3. 우측 폼에 좌표 입력 후 "영역 추가" 클릭
        """)
    
    with col_form:
        st.subheader("➕ 영역 추가")
        
        # 좌표 입력 폼
        with st.form("add_region_form"):
            st.markdown("**새 영역 좌표 입력:**")
            
            col_x, col_y = st.columns(2)
            with col_x:
                x = st.number_input("X (좌측)", min_value=0, max_value=w_orig-1, value=0, step=10)
            with col_y:
                y = st.number_input("Y (상단)", min_value=0, max_value=h_orig-1, value=0, step=10)
            
            col_w, col_h = st.columns(2)
            with col_w:
                w = st.number_input("너비 (W)", min_value=10, max_value=w_orig, value=200, step=10)
            with col_h:
                h = st.number_input("높이 (H)", min_value=10, max_value=h_orig, value=50, step=10)
            
            submitted = st.form_submit_button("➕ 영역 추가", use_container_width=True)
            
            if submitted:
                # 경계 검사
                x = max(0, min(x, w_orig - 10))
                y = max(0, min(y, h_orig - 10))
                w = min(w, w_orig - x)
                h = min(h, h_orig - y)
                
                new_region = {'x': x, 'y': y, 'width': w, 'height': h}
                st.session_state.pending_regions.append(new_region)
                st.success(f"✅ 영역 추가됨: ({x}, {y}) - {w}x{h}")
                st.rerun()
        
        st.divider()
        
        # 대기 중인 영역 목록
        if st.session_state.pending_regions:
            st.markdown(f"**🔴 추가 대기 영역: {len(st.session_state.pending_regions)}개**")
            
            for i, region in enumerate(st.session_state.pending_regions):
                col_info, col_del = st.columns([3, 1])
                with col_info:
                    st.text(f"NEW{i+1}: ({region['x']}, {region['y']}) {region['width']}x{region['height']}")
                with col_del:
                    if st.button("🗑️", key=f"del_pending_{i}"):
                        st.session_state.pending_regions.pop(i)
                        st.rerun()
            
            if st.button("🗑️ 전체 삭제", use_container_width=True):
                st.session_state.pending_regions = []
                st.rerun()
        
        # 기존 확정 영역 목록
        if st.session_state.text_regions:
            st.divider()
            st.markdown(f"**🟢 확정된 영역: {len(st.session_state.text_regions)}개**")
            
            for i, region in enumerate(st.session_state.text_regions):
                bounds = region['bounds']
                text_preview = region['text'][:15] + "..." if len(region['text']) > 15 else region['text']
                st.text(f"{i+1}. ({bounds['x']}, {bounds['y']}) - {text_preview}")
    
    st.divider()
    
    # 하단 버튼
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    
    with col_btn1:
        if st.button("← 이전 단계"):
            st.session_state.current_step = 1
            st.rerun()
    
    with col_btn2:
        # 텍스트 추출 버튼
        total_regions = len(st.session_state.pending_regions)
        if total_regions > 0:
            if st.button(f"📝 {total_regions}개 영역 텍스트 추출 →", type="primary"):
                with st.spinner("🔄 텍스트 추출 중..."):
                    regions = []
                    
                    for i, pending in enumerate(st.session_state.pending_regions):
                        # OCR로 텍스트 추출
                        region = extract_text_from_crop(
                            original_image,
                            pending['x'],
                            pending['y'],
                            pending['width'],
                            pending['height']
                        )
                        
                        region.id = f"region_{len(st.session_state.text_regions) + i:03d}"
                        region.suggested_font_size = max(12, min(int(pending['height'] * 0.7), 72))
                        region.width_scale = 100
                        region.font_filename = "NotoSansKR-Regular.ttf"
                        
                        regions.append(region.to_dict())
                    
                    # 기존 영역에 추가
                    st.session_state.text_regions.extend(regions)
                    st.session_state.pending_regions = []
                    st.session_state.current_step = 3
                    st.rerun()
        else:
            st.button("📝 영역을 먼저 추가하세요", disabled=True)
    
    with col_btn3:
        # 기존 영역이 있으면 바로 편집으로 이동 가능
        if st.session_state.text_regions:
            if st.button("✏️ 기존 영역 편집하기 →"):
                st.session_state.current_step = 3
                st.rerun()

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
                # 영역 좌표 표시
                bounds = region['bounds']
                st.caption(f"📍 위치: ({bounds['x']}, {bounds['y']}) 크기: {bounds['width']}x{bounds['height']}")
                
                # OCR 결과 표시
                if region.get('confidence', 0) > 0:
                    st.caption(f"🔍 OCR 신뢰도: {region.get('confidence', 0):.0f}%")
                
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
                col_save, col_delete = st.columns([2, 1])
                with col_save:
                    if st.button("💾 저장", key=f"save_{region_id}"):
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
                
                with col_delete:
                    if st.button("🗑️ 삭제", key=f"delete_{region_id}"):
                        st.session_state.text_regions = [r for r in st.session_state.text_regions if r['id'] != region_id]
                        if region_id in st.session_state.edited_texts:
                            del st.session_state.edited_texts[region_id]
                        st.rerun()
    
    # 우측: 미리보기
    with col2:
        st.subheader("🖼️ 미리보기")
        
        visualized = draw_regions_on_image(image, regions, st.session_state.edited_texts)
        st.image(
            cv2.cvtColor(visualized, cv2.COLOR_BGR2RGB),
            caption="🟢 텍스트 영역 표시",
            use_column_width=True
        )
        
        # 범례
        st.caption("녹색 박스: 텍스트 영역")
    
    st.divider()
    
    # 네비게이션
    col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 1])
    with col_nav1:
        if st.button("← 영역 추가하기"):
            st.session_state.current_step = 2
            st.rerun()
    with col_nav3:
        if st.button("📤 결과물 생성하기 →", type="primary"):
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
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), use_column_width=True)
        
        with col2:
            st.subheader("결과물")
            st.image(cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB), use_column_width=True)
        
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
                    mime="image/png"
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
                mime="application/json"
            )
        
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        import traceback
        st.code(traceback.format_exc())
    
    st.divider()
    
    # 네비게이션
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← 텍스트 수정하기"):
            st.session_state.current_step = 3
            st.rerun()
    with col_nav2:
        if st.button("🔄 처음부터 다시"):
            st.session_state.current_step = 1
            st.session_state.original_image = None
            st.session_state.text_regions = []
            st.session_state.edited_texts = {}
            st.session_state.pending_regions = []
            st.rerun()

# ==============================================================================
# 사이드바
# ==============================================================================
def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("🖼️ 한글 인포그래픽 교정 도구")
        st.caption("v2.2 - 좌표 입력 방식")
        
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
            st.metric("확정 영역", len(st.session_state.text_regions))
            st.metric("대기 영역", len(st.session_state.pending_regions))
            st.metric("수정된 영역", len(st.session_state.edited_texts))
        
        st.divider()
        
        # 도움말
        with st.expander("❓ 도움말"):
            st.markdown("""
            **사용 방법:**
            1. PNG/JPG 이미지 업로드
            2. 수정할 영역의 좌표 입력
            3. OCR 결과 확인 후 텍스트 수정
            4. 결과물 다운로드
            
            **좌표 확인:**
            - 그림판에서 이미지 열기
            - 마우스 위치의 좌표 확인
            - 또는 이미지 편집 도구 사용
            
            **폰트 추가:**
            `fonts/` 폴더에 .ttf 파일 추가
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

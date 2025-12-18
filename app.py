"""
Korean Infographic Fixer - Streamlit Main App
v2.6 - 스마트 자동 계산 (입력 확정 추적)
"""
import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import os
from datetime import datetime

# Modules
from modules import (
    TextRegion,
    extract_text_from_crop,
    CompositeRenderer,
    MetadataBuilder,
    create_inpainter
)

st.set_page_config(layout="wide", page_title="한글 인포그래픽 교정 도구", page_icon="🖼️")

# ==============================================================================
# 세션 상태 초기화
# ==============================================================================
def init_session_state():
    defaults = {
        'current_step': 1,
        'original_image': None,
        'uploaded_filename': None,
        'text_regions': [],
        'edited_texts': {},
        'pending_regions': [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def init_coord_state():
    """좌표 상태 초기화"""
    # 좌표값
    if 'coord_x1' not in st.session_state:
        st.session_state.coord_x1 = 0
    if 'coord_y1' not in st.session_state:
        st.session_state.coord_y1 = 0
    if 'coord_x2' not in st.session_state:
        st.session_state.coord_x2 = 0
    if 'coord_y2' not in st.session_state:
        st.session_state.coord_y2 = 0
    if 'coord_w' not in st.session_state:
        st.session_state.coord_w = 0
    if 'coord_h' not in st.session_state:
        st.session_state.coord_h = 0
    
    # ★ 입력 확정 여부 (사용자가 직접 수정했는지)
    if 'confirmed_start' not in st.session_state:
        st.session_state.confirmed_start = False  # 시작점 확정 여부
    if 'confirmed_end' not in st.session_state:
        st.session_state.confirmed_end = False    # 끝점 확정 여부
    if 'confirmed_size' not in st.session_state:
        st.session_state.confirmed_size = False   # 크기 확정 여부

# ==============================================================================
# 자동 계산 콜백
# ==============================================================================
def on_start_change():
    """시작점(X1, Y1) 변경 시 - 사용자가 직접 수정함"""
    st.session_state.confirmed_start = True
    recalculate()

def on_end_change():
    """끝점(X2, Y2) 변경 시 - 사용자가 직접 수정함"""
    st.session_state.confirmed_end = True
    recalculate()

def on_size_change():
    """크기(W, H) 변경 시 - 사용자가 직접 수정함"""
    st.session_state.confirmed_size = True
    recalculate()

def recalculate():
    """확정된 값들을 기준으로 나머지 자동 계산"""
    x1 = st.session_state.coord_x1
    y1 = st.session_state.coord_y1
    x2 = st.session_state.coord_x2
    y2 = st.session_state.coord_y2
    w = st.session_state.coord_w
    h = st.session_state.coord_h
    
    confirmed_start = st.session_state.confirmed_start
    confirmed_end = st.session_state.confirmed_end
    confirmed_size = st.session_state.confirmed_size
    
    # Case 1: 시작점 + 끝점 확정 → 크기 계산
    if confirmed_start and confirmed_end and not confirmed_size:
        if x2 > x1 and y2 > y1:
            st.session_state.coord_w = x2 - x1
            st.session_state.coord_h = y2 - y1
    
    # Case 2: 시작점 + 크기 확정 → 끝점 계산
    elif confirmed_start and confirmed_size and not confirmed_end:
        if w > 0 and h > 0:
            st.session_state.coord_x2 = x1 + w
            st.session_state.coord_y2 = y1 + h
    
    # Case 3: 끝점 + 크기 확정 → 시작점 계산 ★ 핵심 케이스
    elif confirmed_end and confirmed_size and not confirmed_start:
        if w > 0 and h > 0 and x2 >= w and y2 >= h:
            st.session_state.coord_x1 = x2 - w
            st.session_state.coord_y1 = y2 - h
    
    # Case 4: 3개 모두 확정됨 - 마지막으로 변경된 것 기준으로 재계산
    elif confirmed_start and confirmed_end and confirmed_size:
        # 가장 최근 변경이 크기면 → 끝점 재계산
        # 가장 최근 변경이 끝점이면 → 크기 재계산
        # 가장 최근 변경이 시작점이면 → 크기 재계산
        # 여기서는 일관성을 위해 크기 기준으로 끝점 재계산
        if w > 0 and h > 0:
            st.session_state.coord_x2 = x1 + w
            st.session_state.coord_y2 = y1 + h

def reset_coords():
    """좌표 입력 완전 초기화"""
    st.session_state.coord_x1 = 0
    st.session_state.coord_y1 = 0
    st.session_state.coord_x2 = 0
    st.session_state.coord_y2 = 0
    st.session_state.coord_w = 0
    st.session_state.coord_h = 0
    st.session_state.confirmed_start = False
    st.session_state.confirmed_end = False
    st.session_state.confirmed_size = False

# ==============================================================================
# 유틸리티 함수
# ==============================================================================
def draw_regions_on_image(image, regions, pending_regions=None):
    vis_image = image.copy()
    pending_regions = pending_regions or []
    
    for i, region in enumerate(regions):
        bounds = region['bounds'] if isinstance(region, dict) else region.bounds
        x, y, w, h = bounds['x'], bounds['y'], bounds['width'], bounds['height']
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(vis_image, f"{i+1}", (x+5, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    for i, region in enumerate(pending_regions):
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(vis_image, f"NEW{i+1}", (x+5, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    return vis_image

def get_available_fonts():
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir)
    fonts = sorted([f for f in os.listdir(fonts_dir) if f.lower().endswith(('.ttf', '.otf'))])
    return fonts if fonts else ["Default"], fonts_dir

# ==============================================================================
# Step 1: 이미지 업로드
# ==============================================================================
def render_step1_upload():
    st.header("📤 Step 1: 이미지 업로드")
    
    uploaded_file = st.file_uploader("인포그래픽 이미지를 업로드하세요", type=['png', 'jpg', 'jpeg', 'webp'])
    
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        st.session_state.original_image = image
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.text_regions = []
        st.session_state.edited_texts = {}
        st.session_state.pending_regions = []
        
        # 좌표 관련 세션 상태 삭제 (새 이미지 업로드 시 초기화)
        for k in ['coord_x1', 'coord_y1', 'coord_x2', 'coord_y2', 'coord_w', 'coord_h',
                  'confirmed_start', 'confirmed_end', 'confirmed_size']:
            if k in st.session_state:
                del st.session_state[k]
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption=uploaded_file.name, use_column_width=True)
        with col2:
            st.success("✅ 업로드 완료!")
            st.info(f"크기: {image.shape[1]} x {image.shape[0]} px")
        
        if st.button("🎯 텍스트 영역 선택 →", type="primary"):
            st.session_state.current_step = 2
            st.rerun()

# ==============================================================================
# Step 2: 텍스트 영역 선택 (스마트 자동 계산)
# ==============================================================================
def render_step2_detect():
    st.header("🎯 Step 2: 텍스트 영역 선택")
    
    if st.session_state.original_image is None:
        st.warning("⚠️ 먼저 이미지를 업로드해주세요.")
        if st.button("← Step 1"):
            st.session_state.current_step = 1
            st.rerun()
        return

    image = st.session_state.original_image
    h_img, w_img = image.shape[:2]
    
    # 좌표 상태 초기화
    init_coord_state()
    
    col_img, col_form = st.columns([2, 1])
    
    with col_img:
        st.subheader("📍 원본 이미지")
        st.caption(f"크기: {w_img} x {h_img} px")
        
        visualized = draw_regions_on_image(image, st.session_state.text_regions, st.session_state.pending_regions)
        st.image(cv2.cvtColor(visualized, cv2.COLOR_BGR2RGB), caption="🟢 확정 | 🔴 대기", use_column_width=True)
        
        st.info("""
        💡 **입력 방법** (아무 조합이나 가능!)
        - **시작점 + 끝점** → 크기 자동 계산
        - **시작점 + 크기** → 끝점 자동 계산  
        - **끝점 + 크기** → 시작점 자동 계산 ⭐
        """)
    
    with col_form:
        st.subheader("➕ 영역 추가")
        
        # 확정 상태 표시
        cs = "✅" if st.session_state.get('confirmed_start', False) else "⬜"
        ce = "✅" if st.session_state.get('confirmed_end', False) else "⬜"
        cz = "✅" if st.session_state.get('confirmed_size', False) else "⬜"
        
        # ========== 좌측 상단 (시작점) ==========
        st.markdown(f"🔹 **좌측 상단 (시작점)** {cs}")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("X1", min_value=0, max_value=w_img-1, step=1,
                           key="coord_x1", on_change=on_start_change)
        with c2:
            st.number_input("Y1", min_value=0, max_value=h_img-1, step=1,
                           key="coord_y1", on_change=on_start_change)
        
        # ========== 우측 하단 (끝점) ==========
        st.markdown(f"🔹 **우측 하단 (끝점)** {ce}")
        c3, c4 = st.columns(2)
        with c3:
            st.number_input("X2", min_value=0, max_value=w_img, step=1,
                           key="coord_x2", on_change=on_end_change)
        with c4:
            st.number_input("Y2", min_value=0, max_value=h_img, step=1,
                           key="coord_y2", on_change=on_end_change)
        
        # ========== 크기 (너비/높이) ==========
        st.markdown(f"🔹 **크기 (너비/높이)** {cz}")
        c5, c6 = st.columns(2)
        with c5:
            st.number_input("너비 (W)", min_value=0, max_value=w_img, step=1,
                           key="coord_w", on_change=on_size_change)
        with c6:
            st.number_input("높이 (H)", min_value=0, max_value=h_img, step=1,
                           key="coord_h", on_change=on_size_change)
        
        st.markdown("---")
        
        # ========== 현재 값 읽기 ==========
        x1 = st.session_state.coord_x1
        y1 = st.session_state.coord_y1
        x2 = st.session_state.coord_x2
        y2 = st.session_state.coord_y2
        w = st.session_state.coord_w
        h = st.session_state.coord_h
        
        # 유효성 검사
        is_valid = (
            x1 >= 0 and y1 >= 0 and
            w >= 10 and h >= 10 and
            x1 + w <= w_img and
            y1 + h <= h_img
        )
        
        # 미리보기
        if w > 0 and h > 0:
            st.success(f"📐 **({x1}, {y1}) → ({x1+w}, {y1+h})** | **{w} x {h}** px")
        else:
            st.warning("⚠️ 좌표를 입력하세요")
        
        # ========== 버튼 영역 ==========
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if is_valid:
                if st.button("➕ 영역 추가", type="primary", use_container_width=True):
                    new_region = {'x': x1, 'y': y1, 'width': w, 'height': h}
                    st.session_state.pending_regions.append(new_region)
                    reset_coords()
                    st.rerun()
            else:
                st.button("➕ 영역 추가", disabled=True, use_container_width=True)
        
        with c_btn2:
            if st.button("🔄 초기화", use_container_width=True):
                reset_coords()
                st.rerun()
        
        if not is_valid and (w > 0 or h > 0):
            st.caption("⚠️ 너비/높이 10px 이상, 이미지 범위 내")
        
        st.markdown("---")
        
        # ========== 대기 영역 목록 ==========
        if st.session_state.pending_regions:
            st.markdown(f"**🔴 대기: {len(st.session_state.pending_regions)}개**")
            for i, r in enumerate(st.session_state.pending_regions):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.caption(f"{i+1}. ({r['x']},{r['y']})→({r['x']+r['width']},{r['y']+r['height']}) {r['width']}x{r['height']}")
                with col_b:
                    if st.button("🗑", key=f"del_{i}"):
                        st.session_state.pending_regions.pop(i)
                        st.rerun()
            
            if st.button("🗑️ 전체 삭제"):
                st.session_state.pending_regions = []
                st.rerun()
        
        # ========== 확정 영역 목록 ==========
        if st.session_state.text_regions:
            st.markdown("---")
            st.markdown(f"**🟢 확정: {len(st.session_state.text_regions)}개**")
    
    st.divider()
    
    # ========== 하단 버튼 ==========
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("← 이전"):
            st.session_state.current_step = 1
            st.rerun()
    with c2:
        n = len(st.session_state.pending_regions)
        if n > 0:
            if st.button(f"📝 {n}개 텍스트 추출 →", type="primary"):
                with st.spinner("추출 중..."):
                    for i, p in enumerate(st.session_state.pending_regions):
                        region = extract_text_from_crop(image, p['x'], p['y'], p['width'], p['height'])
                        region.id = f"region_{len(st.session_state.text_regions)+i:03d}"
                        region.suggested_font_size = max(12, min(int(p['height']*0.7), 72))
                        region.width_scale = 100
                        region.font_filename = "NotoSansKR-Regular.ttf"
                        st.session_state.text_regions.append(region.to_dict())
                    st.session_state.pending_regions = []
                    st.session_state.current_step = 3
                    st.rerun()
        else:
            st.button("📝 영역 먼저 추가", disabled=True)
    with c3:
        if st.session_state.text_regions:
            if st.button("✏️ 편집 →"):
                st.session_state.current_step = 3
                st.rerun()

# ==============================================================================
# Step 3: 텍스트 편집
# ==============================================================================
def render_step3_edit():
    st.header("✏️ Step 3: 텍스트 편집")
    
    if not st.session_state.text_regions:
        st.warning("선택된 영역이 없습니다.")
        if st.button("← Step 2"):
            st.session_state.current_step = 2
            st.rerun()
        return
    
    image = st.session_state.original_image
    regions = st.session_state.text_regions
    fonts, fonts_dir = get_available_fonts()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader(f"📝 영역 ({len(regions)}개)")
        for i, r in enumerate(regions):
            rid = r['id']
            text = r['text']
            disp = text[:20] + "..." if len(text) > 20 else text
            if not disp.strip():
                disp = "(빈 텍스트)"
            
            with st.expander(f"**{i+1}.** {disp}", expanded=(i < 3)):
                b = r['bounds']
                st.caption(f"📍 ({b['x']},{b['y']}) → ({b['x']+b['width']},{b['y']+b['height']}) | {b['width']}x{b['height']}")
                
                cur_text = st.session_state.edited_texts.get(rid, text)
                new_text = st.text_area("텍스트", value=cur_text, key=f"t_{rid}", height=70)
                
                ca, cb = st.columns(2)
                with ca:
                    cur_font = r.get('font_filename', fonts[0])
                    idx = fonts.index(cur_font) if cur_font in fonts else 0
                    font = st.selectbox("폰트", fonts, index=idx, key=f"f_{rid}")
                    size = st.number_input("크기", 8, 120, int(r.get('suggested_font_size', 16)), key=f"s_{rid}")
                with cb:
                    scale = st.number_input("장평%", 50, 150, int(r.get('width_scale', 100)), key=f"sc_{rid}")
                    color = st.color_picker("색상", r.get('text_color', '#000000'), key=f"c_{rid}")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    if st.button("💾 저장", key=f"sv_{rid}"):
                        st.session_state.edited_texts[rid] = new_text
                        for x in st.session_state.text_regions:
                            if x['id'] == rid:
                                x['text'] = new_text
                                x['suggested_font_size'] = size
                                x['width_scale'] = scale
                                x['text_color'] = color
                                x['font_filename'] = font
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"d_{rid}"):
                        st.session_state.text_regions = [x for x in st.session_state.text_regions if x['id'] != rid]
                        st.session_state.edited_texts.pop(rid, None)
                        st.rerun()
    
    with col2:
        st.subheader("🖼️ 미리보기")
        vis = draw_regions_on_image(image, regions)
        st.image(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB), use_column_width=True)
    
    st.divider()
    c1, _, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("← 영역 추가"):
            st.session_state.current_step = 2
            st.rerun()
    with c3:
        if st.button("📤 결과 생성 →", type="primary"):
            st.session_state.current_step = 4
            st.rerun()

# ==============================================================================
# Step 4: 결과물 생성
# ==============================================================================
def render_step4_export():
    st.header("📤 Step 4: 결과물 생성")
    
    if not st.session_state.text_regions:
        st.warning("편집된 영역이 없습니다.")
        return
    
    image = st.session_state.original_image
    regions = st.session_state.text_regions
    
    objs = []
    for r in regions:
        txt = st.session_state.edited_texts.get(r['id'], r['text'])
        objs.append(TextRegion(
            id=r['id'], text=txt, confidence=r.get('confidence', 100),
            bounds=r['bounds'], is_inverted=r.get('is_inverted', False), is_manual=True,
            suggested_font_size=r.get('suggested_font_size', 16),
            text_color=r.get('text_color', '#000000'),
            bg_color=r.get('bg_color', '#FFFFFF'),
            font_filename=r.get('font_filename', 'NotoSansKR-Regular.ttf'),
            width_scale=r.get('width_scale', 100)
        ))
    
    try:
        with st.spinner("생성 중..."):
            inp = create_inpainter("simple_fill")
            bg = inp.remove_all_text_regions(image, objs)
            rend = CompositeRenderer(os.path.join(os.path.dirname(__file__), 'fonts'))
            final = rend.composite(bg, objs, st.session_state.edited_texts)
        
        st.success("✅ 완료!")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("원본")
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), use_column_width=True)
        with c2:
            st.subheader("결과")
            st.image(cv2.cvtColor(final, cv2.COLOR_BGR2RGB), use_column_width=True)
        
        st.divider()
        ok, buf = cv2.imencode(".png", final)
        if ok:
            st.download_button("📥 PNG 다운로드", buf.tobytes(), 
                               f"fixed_{datetime.now().strftime('%H%M%S')}.png", "image/png")
    except Exception as e:
        st.error(f"오류: {e}")
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← 수정"):
            st.session_state.current_step = 3
            st.rerun()
    with c2:
        if st.button("🔄 처음부터"):
            for k in ['original_image', 'text_regions', 'edited_texts', 'pending_regions']:
                st.session_state[k] = [] if 'regions' in k or 'texts' in k else None
            reset_coords()
            st.session_state.current_step = 1
            st.rerun()

# ==============================================================================
# 사이드바
# ==============================================================================
def render_sidebar():
    with st.sidebar:
        st.title("🖼️ 한글 인포그래픽 교정")
        st.caption("v2.6")
        st.divider()
        
        steps = ["1.업로드", "2.영역선택", "3.편집", "4.내보내기"]
        cur = st.session_state.current_step
        for i, s in enumerate(steps, 1):
            if i < cur:
                st.markdown(f"✅ ~~{s}~~")
            elif i == cur:
                st.markdown(f"**🔵 {s}**")
            else:
                st.markdown(f"⚪ {s}")
        
        st.divider()
        if st.session_state.original_image is not None:
            st.metric("확정", len(st.session_state.text_regions))
            st.metric("대기", len(st.session_state.pending_regions))

# ==============================================================================
# 메인
# ==============================================================================
def main():
    init_session_state()
    render_sidebar()
    
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

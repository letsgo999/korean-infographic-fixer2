"""
Text Renderer Module
한글 텍스트를 이미지에 렌더링 (장평 지원)
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import os

from .ocr_engine import TextRegion


class TextRenderer:
    """한글 텍스트 렌더러 (장평 지원)"""
    
    def __init__(self, fonts_dir: Optional[str] = None):
        """
        Args:
            fonts_dir: 폰트 파일 디렉토리 경로
        """
        if fonts_dir:
            self.fonts_dir = Path(fonts_dir)
        else:
            # 기본 폰트 디렉토리 (앱과 같은 위치의 fonts 폴더)
            self.fonts_dir = Path(__file__).parent.parent / "fonts"
        
        self.font_cache = {}
        
    def get_font(
        self, 
        font_filename: str = None,
        font_size: int = 16,
        font_family: str = None,
        font_weight: str = "Regular"
    ) -> ImageFont.FreeTypeFont:
        """
        폰트 객체 가져오기 (캐싱)
        """
        # font_filename이 지정되면 우선 사용
        if font_filename:
            cache_key = f"{font_filename}_{font_size}"
        else:
            cache_key = f"{font_family}_{font_weight}_{font_size}"
        
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        font = None
        
        # 1. font_filename으로 직접 로드 시도
        if font_filename and self.fonts_dir:
            font_path = self.fonts_dir / font_filename
            if font_path.exists():
                try:
                    font = ImageFont.truetype(str(font_path), font_size)
                    self.font_cache[cache_key] = font
                    return font
                except Exception as e:
                    print(f"폰트 로드 실패 ({font_filename}): {e}")
        
        # 2. fonts 디렉토리의 모든 폰트 시도
        if self.fonts_dir and self.fonts_dir.exists():
            for ttf_file in self.fonts_dir.glob("*.ttf"):
                try:
                    font = ImageFont.truetype(str(ttf_file), font_size)
                    self.font_cache[cache_key] = font
                    return font
                except:
                    continue
            
            for otf_file in self.fonts_dir.glob("*.otf"):
                try:
                    font = ImageFont.truetype(str(otf_file), font_size)
                    self.font_cache[cache_key] = font
                    return font
                except:
                    continue
        
        # 3. 시스템 폰트 시도
        system_fonts = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/NanumGothic.ttf",
        ]
        
        for sys_font in system_fonts:
            if Path(sys_font).exists():
                try:
                    font = ImageFont.truetype(sys_font, font_size)
                    self.font_cache[cache_key] = font
                    return font
                except:
                    continue
        
        # 4. 기본 폰트 사용
        try:
            font = ImageFont.load_default()
        except:
            font = None
            
        if font:
            self.font_cache[cache_key] = font
        return font
    
    def render_text_with_scale(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        width_scale: int = 100
    ) -> Image.Image:
        """
        장평을 적용하여 텍스트를 이미지로 렌더링
        
        Args:
            text: 렌더링할 텍스트
            font: 폰트 객체
            width_scale: 장평 (100 = 기본, 90 = 좁게, 110 = 넓게)
            
        Returns:
            텍스트가 렌더링된 RGBA 이미지
        """
        if not text:
            return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        
        # 텍스트 크기 측정
        try:
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            offset_x = -bbox[0]
            offset_y = -bbox[1]
        except:
            # 구 버전 Pillow 호환
            text_width, text_height = font.getsize(text) if hasattr(font, 'getsize') else (len(text) * 12, 20)
            offset_x, offset_y = 0, 0
        
        # 여유 공간 추가
        padding = 4
        img_width = text_width + padding * 2
        img_height = text_height + padding * 2
        
        # 투명 배경 이미지 생성
        text_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)
        
        # 텍스트 그리기 (흰색, 나중에 색상 적용)
        draw.text((padding + offset_x, padding + offset_y), text, font=font, fill=(255, 255, 255, 255))
        
        # 장평 적용 (가로 크기 조정)
        if width_scale != 100:
            new_width = int(img_width * width_scale / 100)
            text_img = text_img.resize((new_width, img_height), Image.LANCZOS)
        
        return text_img
    
    def render_text_on_image(
        self,
        image: np.ndarray,
        region: TextRegion,
        text_override: Optional[str] = None
    ) -> np.ndarray:
        """
        이미지에 텍스트 렌더링 (장평 지원)
        """
        # OpenCV -> PIL
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb).convert('RGBA')
        
        # 텍스트 및 스타일
        text = text_override if text_override is not None else region.text
        if not text:
            return image
        
        font = self.get_font(
            font_filename=region.font_filename,
            font_size=region.suggested_font_size,
            font_family=region.font_family,
            font_weight=region.font_weight
        )
        
        if font is None:
            print(f"폰트를 로드할 수 없습니다: {region.font_filename}")
            return image
        
        # 장평이 적용된 텍스트 이미지 생성
        width_scale = getattr(region, 'width_scale', 100)
        text_img = self.render_text_with_scale(text, font, width_scale)
        
        # 텍스트 색상 적용
        text_color = self._hex_to_rgba(region.text_color)
        
        # 색상 변환
        text_array = np.array(text_img)
        # 흰색 픽셀을 지정된 색상으로 변환
        mask = text_array[:, :, 3] > 0
        text_array[mask, 0] = text_color[0]
        text_array[mask, 1] = text_color[1]
        text_array[mask, 2] = text_color[2]
        text_img = Image.fromarray(text_array)
        
        # 위치 계산 (영역 중앙 정렬 또는 좌상단 정렬)
        x = region.bounds['x']
        y = region.bounds['y']
        
        # 합성
        pil_image.paste(text_img, (x, y), text_img)
        
        # PIL -> OpenCV
        result = cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)
        
        return result
    
    def render_all_regions(
        self,
        image: np.ndarray,
        regions: List[TextRegion],
        text_overrides: Optional[Dict[str, str]] = None
    ) -> np.ndarray:
        """모든 텍스트 영역 렌더링"""
        result = image.copy()
        text_overrides = text_overrides or {}
        
        for region in regions:
            override_text = text_overrides.get(region.id)
            result = self.render_text_on_image(result, region, override_text)
        
        return result
    
    def create_text_layer(
        self,
        width: int,
        height: int,
        regions: List[TextRegion],
        text_overrides: Optional[Dict[str, str]] = None,
        background: Tuple[int, int, int, int] = (0, 0, 0, 0)
    ) -> Image.Image:
        """투명 배경의 텍스트 레이어 생성"""
        layer = Image.new('RGBA', (width, height), background)
        text_overrides = text_overrides or {}
        
        for region in regions:
            text = text_overrides.get(region.id, region.text)
            if not text:
                continue
                
            font = self.get_font(
                font_filename=region.font_filename,
                font_size=region.suggested_font_size,
                font_family=region.font_family,
                font_weight=region.font_weight
            )
            
            if font is None:
                continue
            
            # 장평 적용된 텍스트 이미지
            width_scale = getattr(region, 'width_scale', 100)
            text_img = self.render_text_with_scale(text, font, width_scale)
            
            # 색상 적용
            text_color = self._hex_to_rgba(region.text_color)
            text_array = np.array(text_img)
            mask = text_array[:, :, 3] > 0
            text_array[mask, 0] = text_color[0]
            text_array[mask, 1] = text_color[1]
            text_array[mask, 2] = text_color[2]
            text_img = Image.fromarray(text_array)
            
            # 합성
            x = region.bounds['x']
            y = region.bounds['y']
            layer.paste(text_img, (x, y), text_img)
        
        return layer
    
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """HEX -> RGB 변환"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
        """HEX -> RGBA 변환"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, alpha)


class CompositeRenderer:
    """배경 + 텍스트 레이어 합성 렌더러"""
    
    def __init__(self, fonts_dir: Optional[str] = None):
        self.text_renderer = TextRenderer(fonts_dir)
        
    def composite(
        self,
        background: np.ndarray,
        regions: List[TextRegion],
        text_overrides: Optional[Dict[str, str]] = None
    ) -> np.ndarray:
        """
        배경 이미지 위에 텍스트 합성
        """
        h, w = background.shape[:2]
        
        # 텍스트 레이어 생성
        text_layer = self.text_renderer.create_text_layer(
            w, h, regions, text_overrides
        )
        
        # 배경 이미지를 PIL로 변환
        bg_rgb = cv2.cvtColor(background, cv2.COLOR_BGR2RGB)
        bg_pil = Image.fromarray(bg_rgb).convert('RGBA')
        
        # 합성
        composite = Image.alpha_composite(bg_pil, text_layer)
        
        # OpenCV로 변환
        result = cv2.cvtColor(np.array(composite.convert('RGB')), cv2.COLOR_RGB2BGR)
        
        return result
    
    def preview_with_highlights(
        self,
        image: np.ndarray,
        regions: List[TextRegion],
        highlight_colors: Optional[Dict[str, Tuple[int, int, int]]] = None
    ) -> np.ndarray:
        """텍스트 영역을 하이라이트하여 미리보기 생성"""
        result = image.copy()
        
        default_colors = {
            'normal': (0, 200, 0),
            'inverted': (255, 100, 0),
            'manual': (0, 165, 255),
        }
        colors = highlight_colors or default_colors
        
        for region in regions:
            b = region.bounds
            
            if region.is_manual:
                color = colors.get('manual', (0, 165, 255))
            elif region.is_inverted:
                color = colors.get('inverted', (255, 100, 0))
            else:
                color = colors.get('normal', (0, 200, 0))
            
            cv2.rectangle(
                result,
                (b['x'], b['y']),
                (b['x'] + b['width'], b['y'] + b['height']),
                color,
                2
            )
        
        return result

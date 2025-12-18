"""
OCR Engine Module
텍스트 추출 및 좌표 인식을 담당하는 핵심 모듈
"""
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict

# Tesseract 임포트 (설치되어 있지 않으면 예외 처리)
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


@dataclass
class TextRegion:
    """텍스트 영역 데이터 클래스"""
    id: str
    text: str
    confidence: float
    bounds: Dict[str, int]  # x, y, width, height
    is_inverted: bool = False
    style_tag: str = "body"
    suggested_font_size: int = 16
    text_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    font_family: str = "Noto Sans KR"
    font_weight: str = "Regular"
    font_filename: str = "NotoSansKR-Regular.ttf"  # 실제 폰트 파일명
    width_scale: int = 100  # 장평 (100 = 기본, 90 = 좁게, 110 = 넓게)
    is_manual: bool = False  # 수동 추가 여부
    block_num: int = 0
    line_num: int = 0
    word_count: int = 1
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TextRegion':
        """딕셔너리에서 TextRegion 객체 생성"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def extract_text_from_crop(
    image: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    lang: str = "kor+eng",
    invert_if_dark: bool = True
) -> TextRegion:
    """
    이미지의 특정 영역에서 텍스트 추출
    
    Args:
        image: 원본 이미지 (BGR)
        x, y: 영역 시작 좌표
        width, height: 영역 크기
        lang: OCR 언어
        invert_if_dark: 어두운 배경이면 반전하여 OCR 시도
        
    Returns:
        TextRegion 객체
    """
    # 영역 추출
    h_img, w_img = image.shape[:2]
    x = max(0, min(x, w_img))
    y = max(0, min(y, h_img))
    width = min(width, w_img - x)
    height = min(height, h_img - y)
    
    if width <= 0 or height <= 0:
        return TextRegion(
            id="error",
            text="",
            confidence=0,
            bounds={'x': x, 'y': y, 'width': width, 'height': height}
        )
    
    roi = image[y:y+height, x:x+width].copy()
    
    # BGR -> RGB 변환
    if len(roi.shape) == 3:
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    else:
        roi_rgb = roi
    
    # 배경 밝기 확인
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
    mean_brightness = np.mean(gray)
    is_dark_bg = mean_brightness < 128
    
    # 색상 추출
    text_color, bg_color = _extract_colors(roi_rgb)
    
    # OCR 수행
    text = ""
    confidence = 0.0
    
    if HAS_TESSERACT:
        try:
            # 일반 OCR 시도
            pil_image = Image.fromarray(roi_rgb)
            ocr_result = pytesseract.image_to_data(
                pil_image, 
                lang=lang, 
                output_type=pytesseract.Output.DICT
            )
            
            texts = []
            confidences = []
            for i, txt in enumerate(ocr_result['text']):
                if txt.strip() and int(ocr_result['conf'][i]) > 0:
                    texts.append(txt.strip())
                    confidences.append(int(ocr_result['conf'][i]))
            
            if texts:
                text = ' '.join(texts)
                confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # 어두운 배경이고 결과가 좋지 않으면 반전 시도
            if invert_if_dark and is_dark_bg and (not text or confidence < 50):
                inverted = cv2.bitwise_not(roi_rgb)
                pil_inverted = Image.fromarray(inverted)
                
                ocr_inv = pytesseract.image_to_data(
                    pil_inverted,
                    lang=lang,
                    output_type=pytesseract.Output.DICT
                )
                
                inv_texts = []
                inv_confs = []
                for i, txt in enumerate(ocr_inv['text']):
                    if txt.strip() and int(ocr_inv['conf'][i]) > 0:
                        inv_texts.append(txt.strip())
                        inv_confs.append(int(ocr_inv['conf'][i]))
                
                if inv_texts:
                    inv_text = ' '.join(inv_texts)
                    inv_conf = sum(inv_confs) / len(inv_confs) if inv_confs else 0
                    
                    # 반전 결과가 더 좋으면 사용
                    if inv_conf > confidence:
                        text = inv_text
                        confidence = inv_conf
                        # 반전 이미지의 경우 색상 교체
                        text_color, bg_color = bg_color, text_color
                        
        except Exception as e:
            print(f"OCR 오류: {e}")
            text = ""
            confidence = 0
    
    return TextRegion(
        id=f"crop_{x}_{y}",
        text=text,
        confidence=round(confidence, 1),
        bounds={'x': x, 'y': y, 'width': width, 'height': height},
        is_inverted=is_dark_bg,
        text_color=text_color,
        bg_color=bg_color,
        is_manual=True
    )


def _extract_colors(roi_rgb: np.ndarray) -> Tuple[str, str]:
    """
    영역에서 텍스트 색상과 배경 색상 추출
    
    Returns:
        (text_color_hex, bg_color_hex)
    """
    if roi_rgb.size == 0:
        return "#000000", "#FFFFFF"
    
    pixels = roi_rgb.reshape(-1, 3)
    brightness = np.mean(pixels, axis=1)
    
    dark_pixels = pixels[brightness < 128]
    light_pixels = pixels[brightness >= 128]
    
    if len(dark_pixels) > 0:
        text_color = np.median(dark_pixels, axis=0).astype(int)
    else:
        text_color = np.array([0, 0, 0])
    
    if len(light_pixels) > 0:
        bg_color = np.median(light_pixels, axis=0).astype(int)
    else:
        bg_color = np.array([255, 255, 255])
    
    text_hex = '#{:02x}{:02x}{:02x}'.format(*text_color)
    bg_hex = '#{:02x}{:02x}{:02x}'.format(*bg_color)
    
    return text_hex, bg_hex


class OCREngine:
    """OCR 엔진 클래스"""
    
    def __init__(self, lang: str = "kor+eng", min_confidence: int = 30):
        self.lang = lang
        self.min_confidence = min_confidence
        
    def extract_text_regions(self, image: np.ndarray) -> List[TextRegion]:
        """
        이미지에서 텍스트 영역 추출
        """
        if not HAS_TESSERACT:
            return []
            
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
            
        pil_image = Image.fromarray(image_rgb)
        
        ocr_data = pytesseract.image_to_data(
            pil_image, 
            lang=self.lang, 
            output_type=pytesseract.Output.DICT
        )
        
        regions = []
        n_boxes = len(ocr_data['text'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            
            if text and conf >= self.min_confidence:
                region = TextRegion(
                    id=f"ocr_{len(regions):03d}",
                    text=text,
                    confidence=conf,
                    bounds={
                        'x': ocr_data['left'][i],
                        'y': ocr_data['top'][i],
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i]
                    },
                    block_num=ocr_data['block_num'][i],
                    line_num=ocr_data['line_num'][i],
                    is_inverted=False
                )
                regions.append(region)
                
        return regions


class InvertedRegionDetector:
    """역상 텍스트 영역 감지 클래스"""
    
    def __init__(
        self,
        dark_threshold: int = 150,
        min_area: int = 1000,
        min_width: int = 50,
        min_height: int = 15
    ):
        self.dark_threshold = dark_threshold
        self.min_area = min_area
        self.min_width = min_width
        self.min_height = min_height
        
    def detect(self, image: np.ndarray) -> List[Dict[str, int]]:
        """역상 텍스트가 있을 수 있는 영역 감지"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        lower_orange = np.array([5, 100, 100])
        upper_orange = np.array([25, 255, 255])
        orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
        
        dark_mask = cv2.inRange(gray, 0, self.dark_threshold)
        combined_mask = cv2.bitwise_or(orange_mask, dark_mask)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(
            combined_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            if w >= self.min_width and h >= self.min_height and area >= self.min_area:
                regions.append({'x': x, 'y': y, 'width': w, 'height': h})
                
        return regions


def group_regions_by_lines(regions: List[TextRegion]) -> List[TextRegion]:
    """같은 라인의 텍스트 영역들을 그룹핑"""
    if not regions:
        return []
    
    lines = {}
    
    for region in regions:
        key = (region.block_num, region.line_num)
        
        if key not in lines:
            lines[key] = {
                'texts': [],
                'bounds': [],
                'confidences': [],
                'is_inverted': region.is_inverted
            }
        
        lines[key]['texts'].append(region.text)
        lines[key]['bounds'].append(region.bounds)
        lines[key]['confidences'].append(region.confidence)
    
    line_regions = []
    for key, data in lines.items():
        if not data['bounds']:
            continue
            
        min_x = min(b['x'] for b in data['bounds'])
        min_y = min(b['y'] for b in data['bounds'])
        max_x = max(b['x'] + b['width'] for b in data['bounds'])
        max_y = max(b['y'] + b['height'] for b in data['bounds'])
        
        line_region = TextRegion(
            id=f"line_{len(line_regions):03d}",
            text=' '.join(data['texts']),
            confidence=round(sum(data['confidences']) / len(data['confidences']), 1),
            bounds={
                'x': min_x,
                'y': min_y,
                'width': max_x - min_x,
                'height': max_y - min_y
            },
            word_count=len(data['texts']),
            is_inverted=data['is_inverted']
        )
        line_regions.append(line_region)
    
    line_regions.sort(key=lambda r: r.bounds['y'])
    
    return line_regions


def run_enhanced_ocr(image: np.ndarray) -> Dict:
    """향상된 OCR 파이프라인 실행"""
    ocr_engine = OCREngine()
    inv_detector = InvertedRegionDetector()
    
    normal_regions = ocr_engine.extract_text_regions(image)
    dark_regions = inv_detector.detect(image)
    
    inverted_regions = []
    for region_bounds in dark_regions:
        region = extract_text_from_crop(
            image,
            region_bounds['x'],
            region_bounds['y'],
            region_bounds['width'],
            region_bounds['height'],
            invert_if_dark=True
        )
        if region.text:
            region.is_inverted = True
            inverted_regions.append(region)
    
    all_regions = normal_regions + inverted_regions
    
    return {
        'normal_regions': normal_regions,
        'inverted_regions': inverted_regions,
        'all_regions': all_regions,
        'image_info': {
            'width': image.shape[1],
            'height': image.shape[0]
        }
    }

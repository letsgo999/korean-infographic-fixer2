"""
Style Classifier Module
텍스트 스타일 자동 분류 및 색상 추출
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple
from .ocr_engine import TextRegion


class StyleClassifier:
    """텍스트 스타일 자동 분류기"""
    
    def __init__(self):
        self.style_thresholds = {}
        
    def classify(self, regions: List[TextRegion]) -> List[TextRegion]:
        """높이 기반으로 텍스트 스타일 자동 분류"""
        if not regions:
            return regions
        
        heights = [r.bounds['height'] for r in regions]
        mean_height = np.mean(heights)
        std_height = np.std(heights) if len(heights) > 1 else 0
        
        title_threshold = mean_height + std_height * 0.8
        subtitle_threshold = mean_height + std_height * 0.3
        
        self.style_thresholds = {
            'title': title_threshold,
            'subtitle': subtitle_threshold,
            'mean': mean_height,
            'std': std_height
        }
        
        for region in regions:
            h = region.bounds['height']
            
            if h >= title_threshold:
                region.style_tag = 'title'
                region.suggested_font_size = 32
            elif h >= subtitle_threshold:
                region.style_tag = 'subtitle'
                region.suggested_font_size = 24
            else:
                region.style_tag = 'body'
                region.suggested_font_size = 16
                
        return regions


class ColorExtractor:
    """텍스트 영역 색상 추출기"""
    
    def extract_colors(
        self, 
        image: np.ndarray, 
        regions: List[TextRegion]
    ) -> List[TextRegion]:
        """텍스트 영역의 글자색과 배경색 추출"""
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        for region in regions:
            b = region.bounds
            roi = image_rgb[b['y']:b['y']+b['height'], b['x']:b['x']+b['width']]
            
            if roi.size == 0:
                continue
            
            pixels = roi.reshape(-1, 3)
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
            
            region.text_color = '#{:02x}{:02x}{:02x}'.format(*text_color)
            region.bg_color = '#{:02x}{:02x}{:02x}'.format(*bg_color)
        
        return regions


def apply_styles_and_colors(
    image: np.ndarray, 
    regions: List[TextRegion]
) -> List[TextRegion]:
    """스타일 분류 및 색상 추출 적용"""
    classifier = StyleClassifier()
    color_extractor = ColorExtractor()
    
    regions = classifier.classify(regions)
    regions = color_extractor.extract_colors(image, regions)
    
    return regions

"""
Inpainter Module
텍스트 영역 제거 및 배경 복원 (단순 색상 채우기)
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple
from .ocr_engine import TextRegion


class SimpleInpainter:
    """단순 색상 채우기 방식의 인페인터"""
    
    def __init__(self, padding: int = 2, blur_kernel: int = 0):
        self.padding = padding
        self.blur_kernel = blur_kernel
        
    def remove_text_region(
        self, 
        image: np.ndarray, 
        region: TextRegion,
        fill_color: Tuple[int, int, int] = None
    ) -> np.ndarray:
        """단일 텍스트 영역 제거 및 배경색으로 채우기"""
        result = image.copy()
        b = region.bounds
        
        x1 = max(0, b['x'] - self.padding)
        y1 = max(0, b['y'] - self.padding)
        x2 = min(image.shape[1], b['x'] + b['width'] + self.padding)
        y2 = min(image.shape[0], b['y'] + b['height'] + self.padding)
        
        if fill_color is None:
            fill_color = self._detect_background_color(image, x1, y1, x2, y2)
        
        cv2.rectangle(result, (x1, y1), (x2, y2), fill_color, -1)
        
        return result
    
    def remove_all_text_regions(
        self, 
        image: np.ndarray, 
        regions: List[TextRegion]
    ) -> np.ndarray:
        """모든 텍스트 영역 제거"""
        result = image.copy()
        
        for region in regions:
            result = self.remove_text_region(result, region)
            
        return result
    
    def _detect_background_color(
        self, 
        image: np.ndarray, 
        x1: int, y1: int, x2: int, y2: int,
        sample_width: int = 10
    ) -> Tuple[int, int, int]:
        """영역 주변에서 배경색 감지"""
        h, w = image.shape[:2]
        samples = []
        
        if y1 - sample_width >= 0:
            samples.append(image[max(0, y1-sample_width):y1, x1:x2])
        if y2 + sample_width <= h:
            samples.append(image[y2:min(h, y2+sample_width), x1:x2])
        if x1 - sample_width >= 0:
            samples.append(image[y1:y2, max(0, x1-sample_width):x1])
        if x2 + sample_width <= w:
            samples.append(image[y1:y2, x2:min(w, x2+sample_width)])
        
        if not samples:
            roi = image[y1:y2, x1:x2]
            if roi.size > 0:
                pixels = roi.reshape(-1, 3)
                brightness = np.mean(pixels, axis=1)
                light_pixels = pixels[brightness >= 128]
                if len(light_pixels) > 0:
                    return tuple(np.median(light_pixels, axis=0).astype(int))
            return (255, 255, 255)
        
        all_pixels = np.vstack([s.reshape(-1, 3) for s in samples if s.size > 0])
        
        if len(all_pixels) == 0:
            return (255, 255, 255)
        
        brightness = np.mean(all_pixels, axis=1)
        light_pixels = all_pixels[brightness >= 100]
        
        if len(light_pixels) == 0:
            light_pixels = all_pixels
        
        bg_color = np.median(light_pixels, axis=0).astype(int)
        return tuple(bg_color)


class OpenCVInpainter:
    """OpenCV 인페인팅 알고리즘 사용"""
    
    def __init__(self, method: str = "telea", radius: int = 3):
        self.method = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
        self.radius = radius
        
    def remove_text_region(
        self, 
        image: np.ndarray, 
        region: TextRegion,
        padding: int = 5
    ) -> np.ndarray:
        """OpenCV 인페인팅으로 텍스트 영역 제거"""
        b = region.bounds
        
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
        x1 = max(0, b['x'] - padding)
        y1 = max(0, b['y'] - padding)
        x2 = min(image.shape[1], b['x'] + b['width'] + padding)
        y2 = min(image.shape[0], b['y'] + b['height'] + padding)
        
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
        
        result = cv2.inpaint(image, mask, self.radius, self.method)
        
        return result
    
    def remove_all_text_regions(
        self, 
        image: np.ndarray, 
        regions: List[TextRegion],
        padding: int = 5
    ) -> np.ndarray:
        """모든 텍스트 영역을 한 번에 제거"""
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
        for region in regions:
            b = region.bounds
            x1 = max(0, b['x'] - padding)
            y1 = max(0, b['y'] - padding)
            x2 = min(image.shape[1], b['x'] + b['width'] + padding)
            y2 = min(image.shape[0], b['y'] + b['height'] + padding)
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
        
        result = cv2.inpaint(image, mask, self.radius, self.method)
        
        return result


def create_inpainter(method: str = "simple_fill", **kwargs):
    """인페인터 팩토리 함수"""
    if method == "simple_fill":
        return SimpleInpainter(
            padding=kwargs.get('padding', 2),
            blur_kernel=kwargs.get('blur_kernel', 0)
        )
    elif method in ["telea", "ns"]:
        return OpenCVInpainter(
            method=method,
            radius=kwargs.get('radius', 3)
        )
    else:
        raise ValueError(f"Unknown inpainting method: {method}")

"""
Metadata Builder Module
JSON 메타데이터 생성 및 관리
"""
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from .ocr_engine import TextRegion


class MetadataBuilder:
    """메타데이터 생성 및 관리 클래스"""
    
    def __init__(self):
        self.metadata = {
            'version': '2.0',
            'created_at': None,
            'updated_at': None,
            'image_info': {},
            'ocr_summary': {},
            'text_regions': []
        }
        
    def set_image_info(
        self, 
        filename: str, 
        width: int, 
        height: int,
        **kwargs
    ) -> 'MetadataBuilder':
        """이미지 정보 설정"""
        self.metadata['image_info'] = {
            'filename': filename,
            'width': width,
            'height': height,
            **kwargs
        }
        return self
    
    def set_regions(self, regions: List) -> 'MetadataBuilder':
        """텍스트 영역 설정"""
        self.metadata['text_regions'] = []
        for r in regions:
            if isinstance(r, TextRegion):
                self.metadata['text_regions'].append(r.to_dict())
            elif isinstance(r, dict):
                self.metadata['text_regions'].append(r)
        self._update_summary()
        return self
    
    def add_region(self, region) -> 'MetadataBuilder':
        """텍스트 영역 추가"""
        if isinstance(region, TextRegion):
            self.metadata['text_regions'].append(region.to_dict())
        elif isinstance(region, dict):
            self.metadata['text_regions'].append(region)
        self._update_summary()
        return self
    
    def _update_summary(self):
        """요약 정보 업데이트"""
        regions = self.metadata['text_regions']
        
        if not regions:
            self.metadata['ocr_summary'] = {
                'total_regions': 0,
                'avg_confidence': 0
            }
            return
        
        confidences = [r.get('confidence', 0) for r in regions]
        
        self.metadata['ocr_summary'] = {
            'total_regions': len(regions),
            'manual_regions': len([r for r in regions if r.get('is_manual', False)]),
            'avg_confidence': round(sum(confidences) / len(confidences), 1) if confidences else 0
        }
    
    def build(self) -> Dict:
        """최종 메타데이터 생성"""
        now = datetime.now().isoformat()
        
        if self.metadata['created_at'] is None:
            self.metadata['created_at'] = now
        self.metadata['updated_at'] = now
        
        return self.metadata
    
    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.build(), ensure_ascii=False, indent=indent)
    
    def save(self, filepath: str) -> None:
        """파일로 저장"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, filepath: str) -> 'MetadataBuilder':
        """파일에서 로드"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        builder = cls()
        builder.metadata = data
        return builder
    
    def get_regions(self) -> List[Dict]:
        """텍스트 영역 목록 반환"""
        return self.metadata['text_regions']

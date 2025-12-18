"""
Korean Infographic Fixer - Modules
v2.0 - 캔버스 드래그 선택 방식
"""
from .ocr_engine import (
    TextRegion,
    OCREngine,
    InvertedRegionDetector,
    group_regions_by_lines,
    run_enhanced_ocr,
    extract_text_from_crop,  # 새로 추가
)

from .style_classifier import (
    StyleClassifier,
    ColorExtractor,
    apply_styles_and_colors
)

from .inpainter import (
    SimpleInpainter,
    OpenCVInpainter,
    create_inpainter
)

from .metadata_builder import (
    MetadataBuilder,
)

from .text_renderer import (
    TextRenderer,
    CompositeRenderer
)

from .exporter import (
    PNGExporter,
    PDFExporter,
    MultiFormatExporter
)

__all__ = [
    # OCR
    'TextRegion',
    'OCREngine',
    'InvertedRegionDetector',
    'group_regions_by_lines',
    'run_enhanced_ocr',
    'extract_text_from_crop',
    
    # Style
    'StyleClassifier',
    'ColorExtractor',
    'apply_styles_and_colors',
    
    # Inpainting
    'SimpleInpainter',
    'OpenCVInpainter',
    'create_inpainter',
    
    # Metadata
    'MetadataBuilder',
    
    # Rendering
    'TextRenderer',
    'CompositeRenderer',
    
    # Export
    'PNGExporter',
    'PDFExporter',
    'MultiFormatExporter',
]

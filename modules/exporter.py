"""
Exporter Module
다중 포맷 출력 (PNG, PDF)
"""
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Optional
from io import BytesIO
import json

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class PNGExporter:
    """PNG 이미지 출력"""
    
    def __init__(self, quality: int = 95, dpi: int = 150):
        self.quality = quality
        self.dpi = dpi
        
    def export(
        self, 
        image: np.ndarray, 
        output_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """PNG 파일로 내보내기"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        pil_image.info['dpi'] = (self.dpi, self.dpi)
        
        pil_image.save(
            str(output_path),
            'PNG',
            quality=self.quality,
            dpi=(self.dpi, self.dpi)
        )
        
        if metadata:
            meta_path = output_path.with_suffix('.json')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return str(output_path)
    
    def export_to_bytes(self, image: np.ndarray) -> bytes:
        """메모리에서 PNG 바이트로 변환"""
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG', quality=self.quality)
        return buffer.getvalue()


class PDFExporter:
    """PDF 문서 출력"""
    
    def __init__(
        self, 
        page_size: str = "A4",
        margin: int = 20,
        dpi: int = 150
    ):
        if not HAS_REPORTLAB:
            raise ImportError("reportlab 패키지가 필요합니다")
            
        self.page_size = A4 if page_size == "A4" else letter
        self.margin = margin
        self.dpi = dpi
        
    def export(
        self, 
        image: np.ndarray, 
        output_path: str,
        title: str = "Infographic",
        metadata: Optional[Dict] = None
    ) -> str:
        """PDF 파일로 내보내기"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        c = canvas.Canvas(str(output_path), pagesize=self.page_size)
        page_width, page_height = self.page_size
        
        available_width = page_width - (self.margin * 2)
        available_height = page_height - (self.margin * 2)
        
        img_width, img_height = pil_image.size
        ratio = min(available_width / img_width, available_height / img_height)
        new_width = img_width * ratio
        new_height = img_height * ratio
        
        x = (page_width - new_width) / 2
        y = (page_height - new_height) / 2
        
        img_buffer = BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        c.drawImage(
            ImageReader(img_buffer),
            x, y,
            width=new_width,
            height=new_height
        )
        
        if metadata:
            c.setTitle(title)
            c.setAuthor("Korean Infographic Fixer")
        
        c.save()
        
        return str(output_path)


class MultiFormatExporter:
    """다중 포맷 출력 통합 클래스"""
    
    def __init__(
        self,
        png_quality: int = 95,
        pdf_page_size: str = "A4",
        dpi: int = 150
    ):
        self.png_exporter = PNGExporter(quality=png_quality, dpi=dpi)
        
        try:
            self.pdf_exporter = PDFExporter(page_size=pdf_page_size, dpi=dpi)
        except ImportError:
            self.pdf_exporter = None
    
    def export_all(
        self,
        image: np.ndarray,
        output_dir: str,
        filename_base: str,
        formats: List[str] = ["png"],
        metadata: Optional[Dict] = None
    ) -> Dict[str, str]:
        """여러 포맷으로 동시 내보내기"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for fmt in formats:
            try:
                if fmt.lower() == "png":
                    path = output_dir / f"{filename_base}.png"
                    results["png"] = self.png_exporter.export(image, str(path), metadata)
                    
                elif fmt.lower() == "pdf" and self.pdf_exporter:
                    path = output_dir / f"{filename_base}.pdf"
                    results["pdf"] = self.pdf_exporter.export(image, str(path), metadata=metadata)
                    
            except Exception as e:
                print(f"{fmt} 내보내기 실패: {e}")
                results[fmt] = None
        
        return results
    
    def get_available_formats(self) -> List[str]:
        """사용 가능한 포맷 목록 반환"""
        formats = ["png"]
        if self.pdf_exporter:
            formats.append("pdf")
        return formats

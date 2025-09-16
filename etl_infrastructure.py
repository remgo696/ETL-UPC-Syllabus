"""
Implementaciones concretas de extracción, parsing y persistencia
"""
from pathlib import Path
from typing import List, Dict, Any
from etl_domain import CourseMetadata, Course, Unit, Assessment

class PDFPlumberExtractor:
    def extract_text(self, filepath: Path) -> List[str]:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
        return pages_text

    def extract_tables(self, filepath: Path) -> Dict[str, List[List[str]]]:
        # Implementación real según formato de sílabo
        return {"units": [], "assessments": []}

class UPCSyllabusParser:
    def parse_metadata(self, filename: str) -> CourseMetadata:
        import re
        pattern = re.compile(r"^UG-(?P<period>\d{5})0_(?P<id>[A-Z0-9_\-]{8})-(?P<nrc>\d{4})\.pdf$")
        if match := pattern.match(filename):
            data = match.groupdict()
            year = data['period'][:4]
            term = data['period'][4:]
            return CourseMetadata(
                course_id=data['id'],
                nrc=data['nrc'],
                period=f"{year}-{term}"
            )
        raise ValueError(f"Invalid filename format: {filename}")

    def parse_content(self, text: List[str], tables: Dict) -> Dict[str, Any]:
        # Implementación real según formato de sílabo
        return {}

class JSONRepository:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, course: Course) -> None:
        import json
        filepath = self.base_path / f"{course.metadata.course_id}_{course.metadata.nrc}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._to_dict(course), f, ensure_ascii=False, indent=2)

    def find_by_id(self, course_id: str) -> Course | None:
        import json
        for filepath in self.base_path.glob(f"{course_id}_*.json"):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return self._from_dict(data)
        return None

    def find_by_period(self, period: str) -> List[Course]:
        # Implementación real
        return []

    def _to_dict(self, course: Course) -> Dict:
        return {
            "metadata": {
                "course_id": course.metadata.course_id,
                "nrc": course.metadata.nrc,
                "period": course.metadata.period
            },
            "name": course.name,
            "faculty": course.faculty,
            "credits": course.credits,
            "total_weeks": course.total_weeks,
            "areas": course.areas,
            "units": [],
            "assessments": []
        }

    def _from_dict(self, data: Dict) -> Course:
        # Implementación real
        pass

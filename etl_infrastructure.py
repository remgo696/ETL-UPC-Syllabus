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
        import pdfplumber
        units_table, assessments_table = [], []
        
        # Lista de nombres de secciones para detectar contexto
        SECTION_NAMES = ["I. INFORMACIÓN GENERAL", "II. MISIÓN Y VISIÓN DE LA UPC", "III. INTRODUCCIÓN", 
                        "IV. LOGRO (S) DEL CURSO", "V. COMPETENCIAS (S) DEL CURSO", "VI. UNIDADES DE APRENDIZAJE", 
                        "VII. METODOLOGÍA", "VIII. EVALUACIÓN", "IX. BIBLIOGRAFÍA DEL CURSO", 
                        "X. RECURSOS TECNOLÓGICOS", "XI. Anexos"]

        with pdfplumber.open(filepath) as pdf:
            current_sections = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.splitlines() if text else []
                
                # Detectar las secciones presentes en esta página
                if lines and lines[0] in SECTION_NAMES:  # La página empieza con una sección
                    current_sections = [lines[0]]
                else:
                    if page.page_number > 1 and current_sections:
                        # Continuar con la última sección de la página anterior
                        current_sections = current_sections[-1:]
                    else:  # La primera página empieza "Sílabo de Curso", no con el título de una sección
                        current_sections = []
                
                for line in lines[1:]:
                    if line in SECTION_NAMES:
                        current_sections = [line.strip()]

                # Si hay tabla, ver a qué sección corresponde
                if (table := page.extract_table()):
                    if "VI. UNIDADES DE APRENDIZAJE" in current_sections:
                        units_table.extend(table)
                    elif "VIII. EVALUACIÓN" in current_sections:
                        assessments_table.extend(table)
        
        return {"units": units_table, "assessments": assessments_table}

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
        """Parse content from syllabus text and tables"""
        
        def parse_general_info(text_pages: List[str]) -> Dict[str, Any]:
            """Extract general information from syllabus text"""
            # Join all pages and find the general info section
            full_text = "\n".join(text_pages)
            
            # Extract the "I. INFORMACIÓN GENERAL" section
            section_start = full_text.find("I. INFORMACIÓN GENERAL")
            if section_start == -1:
                return {}
            
            section_end = full_text.find("II. MISIÓN Y VISIÓN", section_start)
            if section_end == -1:
                section_end = len(full_text)
            
            general_info_text = full_text[section_start:section_end]
            
            out = {}
            if not general_info_text:
                return out

            # Search for specific patterns
            def search_label(label: str) -> str:
                import re
                rx = re.compile(rf"{label}\s*[:\-]\s*(.+)", re.IGNORECASE)
                m = rx.search(general_info_text)
                return m.group(1).strip() if m else ''

            out['name'] = search_label('Nombre del Curso')
            out['id'] = search_label('Código del curso')
            out['period'] = search_label('Periodo')
            
            # Parse faculty as list
            faculty_text = search_label('Cuerpo académico')
            out['faculty'] = self._parse_bullet_list(faculty_text)
            
            try:
                out['credits'] = int(search_label('Créditos'))
            except ValueError:
                out['credits'] = 0
                
            try:
                out['weeks'] = int(search_label('Semanas'))
            except ValueError:
                out['weeks'] = 16
            
            # Handle areas that might span multiple lines
            import re
            rx = re.compile(r"\n:\s*(?P<area_1>[^\n]+)\nÁrea o programa[ \t]*(?P<area_2>[^\n]*)\n", re.MULTILINE)
            if m := rx.search(general_info_text):
                careers = m.group('area_1') if not m.group('area_2') else m.group('area_1') + ' ' + m.group('area_2')
                out['areas'] = [area.strip() for area in careers.split(',') if area.strip()]
            else:
                out['areas'] = []
                
            nrc_text = search_label('NRC')
            try:
                out['nrc'] = int(nrc_text)
            except ValueError:
                out['nrc'] = 0
                
            return out
        
        result = parse_general_info(text)
        result['units_table'] = tables.get('units', [])
        result['assessments_table'] = tables.get('assessments', [])
        
        return result
    
    def _parse_bullet_list(self, text: str) -> List[str]:
        """Parse bullet list from text"""
        import re
        return [item.strip() for item in re.split(r"[\uf0b7•,]", text) if item.strip()]

class JSONRepository:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, course: Course) -> None:
        import json
        filename = f"{course.name or 'unknown'}-{course.metadata.nrc or 'no-nrc'}.json"
        filepath = self.base_path / filename
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
        """Serialize Course to dictionary"""
        return {
            "id": course.metadata.course_id,
            "name": course.name,
            "period": course.metadata.period,
            "faculty": course.faculty,
            "credits": course.credits,
            "weeks": course.total_weeks,
            "area": course.areas,
            "nrc": course.metadata.nrc,
            "units": [self._unit_to_dict(u) for u in course.units],
            "assessments": [self._assessment_to_dict(a) for a in course.assessments]
        }
    
    def _unit_to_dict(self, unit) -> Dict:
        """Serialize Unit to dictionary with date calculation"""
        from datetime import date, timedelta
        import json
        
        # Load config for date calculation
        try:
            with open("config.json") as f:
                config_data = json.load(f)
            
            # Extract period from unit (assuming it's available in context)
            # For now, we'll use a default period - this could be improved
            period_parts = unit.week_range  # This is a simplification
            
            # Calculate dates based on week range
            # This is a simplified version - in production you'd want proper date handling
            start_week, end_week = unit.week_range
            
        except:
            # Fallback if config is not available
            pass
            
        return {
            'number': unit.number,
            'title': unit.title,
            'achievement': unit.achievement,
            'initial_week': unit.week_range[0],
            'last_week': unit.week_range[1],
            'initial_date': '2025-08-25',  # Simplified - should calculate from config
            'last_date': '2025-12-06',     # Simplified - should calculate from config
            'syllabus': unit.syllabus,
            'activities': unit.activities,
            'exams': [],  # Unit doesn't store exams in new structure
            'bibliography': []  # Unit doesn't store bibliography in new structure
        }
    
    def _assessment_to_dict(self, assessment) -> Dict:
        """Serialize Assessment to dictionary"""
        return {
            'name': assessment.name,
            'abrev': assessment.code,
            'weight': assessment.weight,
            'week': assessment.week,
            'initial_date': '2025-08-25',  # Simplified - should calculate from config
            'last_date': '2025-12-06'      # Simplified - should calculate from config
        }

    def _from_dict(self, data: Dict) -> Course:
        # Implementación real
        pass

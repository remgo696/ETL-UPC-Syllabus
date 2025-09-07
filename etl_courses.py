"""
El script genera en un .json que incluye información relevante sobre cada curso.
La información se extrae de los archivos PDF de los sílabos en las carpetas de cada curso.
Cada carpeta en el directorio representa un curso y contiene su respectivo archivo PDF de sílabo.
"""

from __future__ import annotations

import os
import re
import json
import pdfplumber
from typing import Optional

class SyllabusRaw:
    """Representa el contenido bruto extraído de un PDF de sílabo.
    """
    SECTION_NAMES = ["I. INFORMACIÓN GENERAL", "II. MISIÓN Y VISIÓN DE LA UPC", "III. INTRODUCCIÓN", "IV. LOGRO (S) DEL CURSO", "V. COMPETENCIAS (S) DEL CURSO", "VI. UNIDADES DE APRENDIZAJE", "VII. METODOLOGÍA", "VIII. EVALUACIÓN", "IX. BIBLIOGRAFÍA DEL CURSO", "X. RECURSOS TECNOLÓGICOS", "XI. Anexos"]
    FILENAME_PATTERN = re.compile(r"^UG-(?P<period>\d{6})_(?P<id>[A-Z0-9_\-]{8})-(?P<nrc>\d{4})\.pdf$")

    def __init__(self, filepath: str, raw_text: list[str], unidades_table: list[list[str]], evaluacion_table: list[list[str]]):
        self.filepath = filepath
        self.raw_text = raw_text      # texto crudo, listado por página
        self.unidades_table = unidades_table  # tabla cruda
        self.evaluacion_table = evaluacion_table  # tabla cruda
    
    @property
    def filename(self):
        return os.path.basename(self.filepath)

    @property
    def parsed_filename(self) -> dict:
        """Extraer metadatos crudos del nombre del archivo.
            Diccionario con claves: period, id (course code), nrc
        """
        m = self.FILENAME_PATTERN.match(self.filename)
        if not m:
            return {}
        return m.groupdict()
    
    def _get_section(self,section_name:str):
        if section_name not in self.SECTION_NAMES:
            raise ValueError(f"Section name '{section_name}' is not recognized.")
        in_section = False
        section_content = []
        for page in self.raw_text:
            lines = page.splitlines()
            for line in lines:
                if section_name in line:
                    in_section = True
                    continue
                if in_section:
                    if line in self.SECTION_NAMES:
                        break
                    # Si estamos en la sección, extraemos el texto.
                    section_content.append(line)
        return "\n".join(section_content)
    
    @property
    def general_info(self) -> str:
        """Extrae y devuelve la sección de "I. INFORMACIÓN GENERAL" del texto crudo.
        """
        return self._get_section(self, self.SECTION_NAMES[0]) 

    @classmethod
    def from_pdf(cls, filepath: str) -> "SyllabusRaw":
        # import pdfplumber
        raw_text, unidades_table, evaluacion_table = [], [], []

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                # Guardo el texto en crudo
                raw_text.append(text)

                # Detectar las secciones presentes en esta página.
                lines = text.splitlines() if text else []
                # Si la primera línea no es el título de una sección, significa que sigue la sección de la página anterior.
                if lines[0] in cls.SECTION_NAMES: # La página empieza con una sección
                    current_sections = [lines[0]]
                else:
                    if page.page_number > 1:
                        # Continuar con la última sección de la página anterior
                        current_sections = current_sections[-1:]
                    else: # La primera página empieza "Sílabo de Curso", no con el título de una sección
                        current_sections = []
                
                for line in lines[1:]:
                    if line in cls.SECTION_NAMES:
                        current_sections = [line.strip()]

                # Si hay tabla, ver a qué sección corresponde
                table = page.extract_table()
                if table:
                    if "VI. UNIDADES DE APRENDIZAJE" in current_sections:
                        unidades_table = table
                    elif "VIII. EVALUACIÓN" in current_sections:
                        evaluacion_table = table
    
        return cls(filepath, raw_text, unidades_table, evaluacion_table)

    @classmethod
    def find_syllabi(cls, directory: str) -> list[str]:
        """
        Buscar recursivamente todos los archivos PDF de sílabos que cumplan el patrón en `directory`.
        Devuelve una lista de rutas absolutas a PDFs que coinciden.
        """
        matches: list[str] = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.pdf') and cls.FILENAME_PATTERN.match(file):
                    matches.append(os.path.join(root, file))
        return matches

class Course:
    """Representa un curso académico.
    """
    def __init__(self, course_code: str, name: str = "", period: str = "", faculty: str = "", credits: Optional[int] = None, weeks: Optional[int] = None, area: str = "", nrc: str = ""):
        self.course_id: str = course_code
        self.course_name: str = name
        self.period: str = period
        self.faculty: str = faculty
        self.credits: Optional[int] = credits
        self.weeks: Optional[int] = weeks
        self.area: str = area
        self.nrc: str = nrc
        self.units: list['Unit'] = []

    def __str__(self):
        return f'Course "{self.course_name}" ({self.course_id}), NRC: {self.nrc}'
    
    @classmethod
    def from_raw(cls, raw_data: SyllabusRaw) -> 'Course':
        """Crear una instancia de Course a partir de datos crudos extraído
        """
        

        parsed = cls._parse_general_info(raw_data.general_info)
        #¿Aquí se toma unit_table y exam_table para convertirlas en list[Unit] y list[Exam]?
        course.units = cls._parse_units(raw_data.unit_table)
        course.evaluations = cls._parse_evaluations(raw_data.exam_table)

        # Preferir valores extraídos del texto; si faltan, usar los del filename
        if (pdf_course_code:=parsed.get('course_id')) and pdf_course_code != course_code:
            print(f"Warning: Course code mismatch between filename and PDF content: {course_code} vs {pdf_course_code}")
            course_code = pdf_course_code
        if (pdf_nrc := parsed.get('nrc')) and pdf_nrc != nrc:
            print(f"Warning: NRC mismatch between filename and PDF content: {nrc} vs {pdf_nrc}")
            nrc = pdf_nrc

        # Creo un objeto Course con los datos extraídos
        course = cls(course_code=course_code, 
                     name=parsed.get('course_name'), 
                     period=parsed.get('period'), 
                     faculty=parsed.get('faculty'), 
                     credits=parsed.get('credits'), 
                     weeks=parsed.get('weeks'), 
                     area=parsed.get('area'), 
                     nrc=nrc)
        return course

    @staticmethod
    def _parse_general_info(text: str) -> dict:
        """Heurísticas simples para extraer campos del título "I. INFORMACIÓN GENERAL" de un sílabo.

        Esto es intencionalmente conservador: busca líneas con prefijos conocidos.
        Devuelve un dict con claves como 'course_name', 'course_id', 'period', 'faculty', 'credits', 'weeks', 'area', 'nrc'.
        """

        # Ejemplo de "I. INFORMACIÓN GENERAL":
        # Nombre del Curso : Análisis de Circuitos Eléctricos 2
        # Código del curso : 1AEL0244
        # Periodo : UG-2do Semestre 2025 Pregrado
        # Cuerpo académico :  Rojas Quispe, Ricardo Valentin
        # Créditos : 4
        # Semanas : 16
        # Área o programa : INGENIERÍA BIOMÉDICA,INGENIERÍA ELECTRÓNICA
        # NRC (Código de Registro de Nombre) : 8281

        out = {}
        if not text:
            return out

        # Normalizar saltos y espacios
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        joined = "\n".join(lines)

        # Buscar patrones clave
        def search_label(label):
            rx = re.compile(rf"{label}\s*[:\-]\s*(.+)", re.IGNORECASE)
            m = rx.search(joined)
            return m.group(1).strip() if m else None

        out['course_name'] = search_label('Nombre del Curso') or search_label('Nombre')
        out['course_id'] = search_label('Código del curso') or search_label('Código')
        out['period'] = search_label('Periodo') or search_label('Periodo')
        out['faculty'] = search_label('Cuerpo académico') or search_label('Catedr')
        area = search_label('Área o programa') or search_label('Area')
        out['area'] = area

        credits = search_label('Créditos')
        if credits:
            m = re.search(r"(\d+)", credits)
            out['credits'] = int(m.group(1)) if m else None

        weeks = search_label('Semanas')
        if weeks:
            m = re.search(r"(\d+)", weeks)
            out['weeks'] = int(m.group(1)) if m else None

        nrc = re.search(r"NRC\s*[:\-]?\s*(\d+)", joined, re.IGNORECASE)
        if nrc:
            out['nrc'] = nrc.group(1)

        return out

    def to_dict(self) -> dict:
        return {
            'course_id': self.course_id,
            'course_name': self.course_name,
            'period': self.period,
            'faculty': self.faculty,
            'credits': self.credits,
            'weeks': self.weeks,
            'area': self.area,
            'nrc': self.nrc,
            'units': [u.__dict__ for u in self.units],
        }

    def save_json(self, dest_dir: str) -> str:
        """Guardar la representación JSON del curso en dest_dir y devolver la ruta del archivo."""
        os.makedirs(dest_dir, exist_ok=True)
        filename = f"{self.course_id or 'unknown'}-{self.nrc or 'no-nrc'}.json"
        path = os.path.join(dest_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

class Unit:
    """
    Ejemplo de unidad
    Unidad n. 1: Respuesta Completa de Sistemas de Segundo Orden
    COMPETENCIA (S):
    LOGRO DE LA UNIDAD: Al finalizar la unidad, el estudiante compara resultados teóricos, simulados y
    experimentales en circuitos eléctricos con régimen transitorio.

    SEMANA | TEMARIO | ACTIVIDADES DE APRENDIZAJE | EVIDENCIAS DE APRENDIZAJE | BIBLIOGRAFÍA
    """

    def __init__(self, number, title, achievement):
        self.number = number
        self._title = title
        self._achievement = achievement
        self._weeks = []

    @property
    def title(self):
        return f"Unidad n. {self.number}: {self._title}"

    @property
    def achievement(self):
        return self._achievement

    @property
    def weeks(self):
        return self._weeks
    
class Exam:
    """
    Ejemplo de evaluación
    Cronograma
    TIPO | COMPETENCIA | PESO | SEMANA | OBSERVACIÓN | RECUPERABLE
    """
    def __init__(self, type, weight, week):
        self.type = type
        self.weight = weight
        self.week = week

#ETL
def extract(directory: str) -> list[SyllabusRaw]:
    """Recorrer subdirectorios, encontrar PDFs de sílabos, leerlos en raw."""
    syllabi_raw = []
    syllabi_path = SyllabusRaw.find_syllabi(directory)
    print(f'Extracting syllabi from {len(syllabi_path)} PDF files in "{directory}"')
    for pdfpath in syllabi_path:
        raw = SyllabusRaw.from_pdf(pdfpath)
        syllabi_raw.append(raw)
        print(f'File processed: "{raw.filename}"')

    return syllabi_raw

def transform(syllabi: list[SyllabusRaw]) -> list[Course]:
    courses = []
    for syllabus in syllabi:
        course = Course.from_raw(syllabus)
        courses.append(course)
    return courses

def load():
    pass

cwd = os.getcwd()
syllabi_raw = extract(cwd)

courses = transform(syllabi_raw)

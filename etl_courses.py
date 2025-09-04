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

class Course:
    """
    Representa un curso académico.
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
    def from_pdf(cls, filepath: str) -> 'Course':
        """Crear una instancia de Course a partir del PDF del sílabo.

        Estrategia:
        - Usar el nombre de archivo para extraer código y NRC (regex comprobada).
        - Extraer texto del PDF (pdfplumber) y aplicar heurísticas/regex para campos comunes.
        - Devolver un objeto Course (campos faltantes quedan vacíos o None).

        Ejemplo de informacion del curso:
        INFORMACIÓN GENERAL
        Nombre del Curso : Análisis de Circuitos Eléctricos 2
        Código del curso : 1AEL0244
        Periodo : UG-2do Semestre 2025 Pregrado
        Cuerpo académico :  Rojas Quispe, Ricardo Valentin
        Créditos : 4
        Semanas : 16
        Área o programa : INGENIERÍA BIOMÉDICA,INGENIERÍA ELECTRÓNICA
        NRC (Código de Registro de Nombre) : 8281
        """
        filename = os.path.basename(filepath)
        # Primero, intentar extraer datos del filename
        fname_re = re.compile(r"^UG-(\d{6})_([A-Za-z0-9_\-]+)-(\d+)\.?pdf$", re.IGNORECASE)
        m = fname_re.match(filename)
        course_code = ""
        nrc = ""
        period_code = ""
        if m:
            period_code = m.group(1)
            course_code = m.group(2)
            nrc = m.group(3)

        # Extraer texto del PDF (concatenar páginas)
        text = ""
        try:
            with pdfplumber.open(filepath) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
                text = "\n".join(pages)
        except Exception:
            # No queremos que falle el proceso entero por un PDF corrupto
            text = ""

        parsed = cls._parse_syllabus_text(text)

        # Preferir valores extraídos del texto; si faltan, usar los del filename
        name = parsed.get('course_name') or ""
        period = parsed.get('period') or period_code
        faculty = parsed.get('faculty') or ""
        credits = parsed.get('credits')
        weeks = parsed.get('weeks')
        area = parsed.get('area') or ""

        course = cls(
            course_code=course_code or parsed.get('course_id', ''),
            name=name,
            period=period,
            faculty=faculty,
            credits=credits,
            weeks=weeks,
            area=area,
            nrc=nrc or parsed.get('nrc', ''),
        )
        return course

    @classmethod
    def find_course_path(cls, directory: str) -> list[str]:
        """Buscar todos los archivos PDF de sílabos que cumplan el patrón en `directory`.

        Devuelve una lista de rutas absolutas a PDFs que coinciden.
        """
        matches: list[str] = []
        pattern = re.compile(r"^UG-(\d{6})_([A-Za-z0-9_\-]+)-(\d+)\.?pdf$", re.IGNORECASE)
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.lower().endswith('.pdf'):
                if pattern.match(entry.name):
                    matches.append(entry.path)
        return matches

    @staticmethod
    def _parse_syllabus_text(text: str) -> dict:
        """Heurísticas simples para extraer campos del texto de un sílabo.

        Esto es intencionalmente conservador: busca líneas con prefijos conocidos.
        Devuelve un dict con claves como 'course_name', 'course_id', 'period', 'faculty', 'credits', 'weeks', 'area', 'nrc'.
        """
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
def extract():
    """Recorrer subdirectorios, encontrar PDFs de sílabos, crear objetos Course."""
    syllabus_files = []
    cwd = os.getcwd()
    for entry in os.scandir(cwd):
        if entry.is_dir():
            found = Course.find_course_path(entry.path)
            for pdfpath in found:
                syllabus_files.append(pdfpath)
                course = Course.from_pdf(pdfpath)
                outpath = course.save_json(entry.path)
                print(f"Saved: {outpath}")
    print(f"Processed {len(syllabus_files)} syllabus PDFs")

    # Abro cada archivo en syllabus_files y extraigo las tablas que están debajo 
    # de los títulos UNIDADES DE APRENDIZAJE y EVALUACIÓN
    is_unit_table=is_exam_table=False
    for syllabus in syllabus_files:
        unit_table=[]
        exam_table=[]
        print(f"\nExtrayendo datos de {syllabus}...\n")
        with pdfplumber.open(syllabus) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if "UNIDADES DE APRENDIZAJE" in text: #de aquí en adelante está la tabla de unidades
                    is_unit_table = True
                elif "METODOLOGÍA" in text: #aquí termina la tabla de unidades
                    is_unit_table = False
                elif "EVALUACIÓN" in text: #de aquí en adelante está la tabla de evaluación
                    is_exam_table = True
                elif "BIBLIOGRAFÍA DEL CURSO" in text: #aquí termina la tabla de evaluación
                    is_exam_table = False
                
                if is_unit_table:
                    # Extraer información de las unidades
                    unit_table.append(page.extract_table())
                elif is_exam_table:
                    # Extraer información de las evaluaciones
                    exam_table.append(page.extract_table())
        print(unit_table)
        print(exam_table)

def transform():
    pass

def load():
    pass

extract()
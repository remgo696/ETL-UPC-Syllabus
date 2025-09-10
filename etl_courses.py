"""
El script genera en un .json que incluye información relevante sobre cada curso.
La información se extrae de los archivos PDF de los sílabos en las carpetas de cada curso.
Cada carpeta en el directorio representa un curso y contiene su respectivo archivo PDF de sílabo.
"""

from __future__ import annotations

import os
import re
import json
from datetime import date, timedelta
from typing import Optional

class Config:
    def __init__(self, source="config.json"):
        self.source = source
        self._data = self._load()
    
    def _load(self):
        with open(self.source) as f:
            return json.load(f)

    def start_date(self, period: str) -> date:
        return date.fromisoformat(self._data[period]["start_date"])

    def end_date(self, period: str) -> date:
        return date.fromisoformat(self._data[period]["end_date"])
config = Config()

class SyllabusRaw:
    """Representa el contenido bruto extraído de un PDF de sílabo.
    """
    SECTION_NAMES = ["I. INFORMACIÓN GENERAL", "II. MISIÓN Y VISIÓN DE LA UPC", "III. INTRODUCCIÓN", "IV. LOGRO (S) DEL CURSO", "V. COMPETENCIAS (S) DEL CURSO", "VI. UNIDADES DE APRENDIZAJE", "VII. METODOLOGÍA", "VIII. EVALUACIÓN", "IX. BIBLIOGRAFÍA DEL CURSO", "X. RECURSOS TECNOLÓGICOS", "XI. Anexos"]
    FILENAME_PATTERN = re.compile(r"^UG-(?P<period>\d{5})0_(?P<id>[A-Z0-9_\-]{8})-(?P<nrc>\d{4})\.pdf$")
    # nrc: numero de referencia del curso
    # id: codigo del curso


    def __init__(self, filepath: str, raw_text: list[str], units_table: list[list[str]], assessments_table: list[list[str]]):
        self.filepath = filepath
        self.raw_text = raw_text      # texto crudo, listado por página
        self.units_table = units_table  # tabla cruda
        self.assessments_table = assessments_table  # tabla cruda
    
    @property
    def filename(self):
        return os.path.basename(self.filepath)
    
    def _parse_filename(self) -> dict:
        """Extraer metadatos crudos del nombre del archivo.
            Diccionario con claves: period, id (course code), nrc
        """
        m = self.FILENAME_PATTERN.match(self.filename)
        if not m:
            return {}
        return m.groupdict()
    
    @property
    def period(self) -> str:
        # Retorna el periodo en formato "YYYY-T", por ejemplo, "2025-2"
        year = self._parse_filename().get('period', '')[:4]
        term = self._parse_filename().get('period', '')[4:]
        return f"{year}-{term}"
    @property
    def id(self) -> str:
        return self._parse_filename().get('id', '')
    @property
    def nrc(self) -> str:
        return self._parse_filename().get('nrc', '')
    
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
                    # Si encontramos otra sección, terminamos.
                    if line in self.SECTION_NAMES:
                        break
                    # Si estamos en la sección, extraemos el texto.
                    section_content.append(line)
        return "\n".join(section_content)
    
    @property
    def general_info(self) -> str:
        """Extrae y devuelve la sección de "I. INFORMACIÓN GENERAL" del texto crudo.
        """
        return self._get_section(self.SECTION_NAMES[0]) 

    @classmethod
    def from_pdf(cls, filepath: str) -> "SyllabusRaw":
        import pdfplumber
        raw_text, units_table, assessments_table = [], [], []

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                # Guardo el texto en crudo
                raw_text.append(text)

                # Detectar las secciones presentes en esta página.
                lines = text.splitlines() if text else []
                # Si la primera línea no es el título de una sección, 
                # significa que sigue la sección de la página anterior.
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
                if (table := page.extract_table()):
                    if "VI. UNIDADES DE APRENDIZAJE" in current_sections:
                        units_table.extend(table)
                    elif "VIII. EVALUACIÓN" in current_sections:
                        assessments_table.extend(table)
    
        return cls(filepath, raw_text, units_table, assessments_table)

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
    def __init__(self, id: str, name: str = "", period: str = "", faculty: list[str] = "", credits: Optional[int] = None, weeks: Optional[int] = None, area: list[str] = [], nrc: str = "", units: list['Unit']=[], assessments: list['Exam']=[]):
        self.id: str = id
        self.name: str = name
        self.period: str = period
        self.faculty: str = faculty
        self.credits: Optional[int] = credits
        self.weeks: Optional[int] = weeks
        self.area: str = area
        self.nrc: str = nrc
        self.units: list['Unit'] = units
        self.assessments: list['Exam'] = assessments

    def __str__(self):
        return f'{self.id}-{self.name} (NRC: {self.nrc})'
    
    @classmethod
    def from_raw(cls, raw_data: SyllabusRaw) -> 'Course':
        """Crear una instancia de Course a partir de datos crudos extraído
        """
        def parse_general_info(text: str) -> dict: 
            """Heurísticas simples para extraer campos del título "I. INFORMACIÓN GENERAL" de un sílabo. Esto es intencionalmente conservador: busca líneas con prefijos conocidos. Devuelve un dict con claves como 'name', 'id', 'period', 'faculty', 'credits', 'weeks', 'area', 'nrc'. """
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

            # Buscar patrones clave
            def search_label(label: str) -> str:
                rx = re.compile(rf"{label}\s*[:\-]\s*(.+)", re.IGNORECASE)
                m = rx.search(text)
                return m.group(1) if m else ''

            out['name'] = search_label('Nombre del Curso')
            out['id'] = search_label('Código del curso')
            out['period'] = search_label('Periodo')
            out['faculty'] = parse_bullet_list(search_label('Cuerpo académico'))
            credits = search_label('Créditos')
            if credits:
                m = re.search(r"(\d+)", credits)
                out['credits'] = int(m.group(1)) if m else None
            weeks = search_label('Semanas')
            if weeks:
                m = re.search(r"(\d+)", weeks)
                out['weeks'] = int(m.group(1)) if m else None
            careers = search_label('Área o programa')
            out['area'] = careers.split(',') if careers else []
            nrc = search_label('NRC')
            try:
                out['nrc'] = int(nrc)
            except ValueError:
                print(f"Warning: NRC value '{nrc}' is not an integer.")
            return out

        # Parsear la información general
        parsed = parse_general_info(raw_data.general_info)
        
        # Se prefieren los valores extraídos del texto. Advertir si hay discrepancias.
        if (parsed_id := parsed.get('id')) != (filename_id := raw_data.id):
            print(f"Warning: Course ID mismatch between filename and PDF content: <{parsed_id}> vs <{filename_id}>")
        if str(parsed_nrc := parsed.get('nrc')) != (filename_nrc := raw_data.nrc):
            print(f"Warning: NRC mismatch between filename and PDF content: <{parsed_nrc}> vs <{filename_nrc}>")

        units = Unit.from_raw(raw_data.units_table, raw_data.period)
        assessments = Exam.from_raw(raw_data.assessments_table, raw_data.period)

        # Creo un objeto Course con los datos extraídos
        course = cls(id=parsed_id, 
                     name=parsed.get('name'), 
                     period=parsed.get('period'), 
                     faculty=parsed.get('faculty'), 
                     credits=parsed.get('credits'), 
                     weeks=parsed.get('weeks'), 
                     area=parsed.get('area'), 
                     nrc=parsed_nrc,
                     units=units,
                     assessments=assessments)

        return course

    @classmethod
    def from_json(cls, path: str) -> 'Course':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> 'Course':
        units = [Unit(**u) for u in data.get('units', [])]
        assessments = [Exam(**a) for a in data.get('assessments', [])]
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            period=data.get('period', ''),
            faculty=data.get('faculty', []),
            credits=data.get('credits'),
            weeks=data.get('weeks'),
            area=data.get('area', []),
            nrc=data.get('nrc', ''),
            units=units,
            assessments=assessments
        )
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'period': self.period,
            'faculty': self.faculty,
            'credits': self.credits,
            'weeks': self.weeks,
            'area': self.area,
            'nrc': self.nrc,
            'units': [u.to_dict() for u in self.units],
            'assessments': [a.to_dict() for a in self.assessments],
        }

    def to_json(self, dest_dir: str) -> str:
        """Guardar la representación JSON del curso en dest_dir y devolver la ruta del archivo."""
        os.makedirs(dest_dir, exist_ok=True)
        filename = f"{self.name or 'unknown'}-{self.nrc or 'no-nrc'}.json"
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

    def __init__(self, number: int, title: str, achievement: str, init_week: int, end_week: int, syllabus: list[str], period: str, activities: list[str]=[], exams: list[str]=[], bibliography: list[str]=[]):
        self.number = number
        self.title = title
        self.achievement = achievement
        self.init_week = init_week
        self.end_week = end_week
        self.syllabus = syllabus
        self.period = period
        self.exams = exams
        self.activities = activities
        self.bibliography = bibliography
    
    def to_dict(self) -> dict:
        init_date, end_date = weeks_to_dates(self.period, self.init_week, self.end_week)
        return {
            'number': self.number,
            'title': self.title,
            'achievement': self.achievement,
            'initial_week': self.init_week,
            'last_week': self.end_week,
            'initial_date': init_date.isoformat(),
            'last_date': end_date.isoformat(),
            'syllabus': self.syllabus,
            'activities': self.activities,
            'exams': self.exams,
            'bibliography': self.bibliography,
        }

    @classmethod
    def from_raw(cls, table: list[list[str]], period: str) -> list[Unit]:
        """Parsea la tabla de unidades y devuelve una lista de instancias Unit.
        period: periodo académico en formato "YYYY-T", por ejemplo, "2025-2"
        """
        header = ['SEMANA', 'TEMARIO', 'ACTIVIDADES DE\nAPRENDIZAJE', 'EVIDENCIAS DE\nAPRENDIZAJE', 'BIBLIOGRAFÍA']
        units = []
        i=-1
        while i < len(table)-1:
            row = table[i := i + 1]
            if row[0].startswith("Unidad n."): #Empiezan las unidades
                # Extraer número y título
                match = re.match(r"^Unidad n\. (?P<numero>\d+): (?P<titulo>.+)", row[0])
                if match:
                    number = int(match.group("numero"))
                    title = match.group("titulo")
            else:
                continue
            row = table[i := i + 1]    # La siguiente fila deberían ser las competencias. Las ignoro por ahora
            if row[0].startswith("COMPETENCIA (S):"):
                pass
            else:
                continue
            row = table[i := i + 1]    # La siguiente fila debería ser el logro
            if row[0].startswith("LOGRO DE LA UNIDAD:"):
                _, achievement = row[0].split(":", 1)
                achievement = achievement.strip()
            else:
                continue
            row = table[i := i + 1]    # Las siguientes filas contienen la tabla que describe la unidad en sí
            if row[0] != header[0]:
                continue
            row = table[i := i + 1]
            if row[0].startswith("Semana"):
                row = [field.replace("\n", " ") for field in row]  #limpio los campos
                parsed = re.match(r"Semana (?P<semana1>[\d,\s-]+) - (?P<semana2>[\d,\s-]+)", row[0])
                if parsed:
                    # Extraer semanas
                    week1 = int(parsed.group("semana1"))
                    week2 = int(parsed.group("semana2"))
                syllabus = parse_bullet_list(row[1])
                activities = parse_bullet_list(row[2])
                exams = parse_bullet_list(row[3])
                bibliography = parse_bullet_list(row[4])
            else:
                continue
            units.append(
                cls(number, title, achievement, week1, week2, syllabus=syllabus, period=period, activities=activities, exams=exams, bibliography=bibliography))
        return units
    
class Exam:
    """
    Ejemplo de evaluación
    Cronograma
    TIPO | COMPETENCIA | PESO | SEMANA | OBSERVACIÓN | RECUPERABLE
    """
    def __init__(self, name: str, abrev: str, weight: float, period: str, week: int):
        self.name = name
        self.abrev = abrev
        self.weight = weight
        self.period = period
        self.week = week
    
    def to_dict(self) -> dict:
        init_date, end_date = weeks_to_dates(self.period, self.week)
        return {
            'name': self.name,
            'abrev': self.abrev,
            'weight': self.weight,
            'week': self.week,
            'initial_date': init_date.isoformat(),
            'last_date': end_date.isoformat(),
        }
    @classmethod
    def from_raw(cls, table: list[list[str]], period: str) -> list[Exam]:
        header = ['TIPO', 'COMPETENCIA', 'PESO', 'SEMANA', 'OBSERVACIÓN', 'RECUPERABLE']
        exams = []
        for row in table:
            if row == header:
                continue  # Saltar las filas de encabezado. Normalmente se repiten en las filas impares
            row = [field.strip() for field in row]
            name, abrev = row[0].split('-', 1) if '-' in row[0] else (row[0], '')
            # Validar y convertir semana a entero
            week_raw = row[3]
            try:
                week = int(week_raw)
            except (ValueError, TypeError):
                print(f"Warning: Invalid week value '{week_raw}' in exam '{name}'. Skipping this exam.")
                continue
            try:
                weight = float(row[2][:-1])  # Quitar el símbolo de porcentaje si está presente
            except (ValueError, TypeError):
                print(f"Warning: Invalid weight value '{row[2]}' in exam '{name}'. Setting weight to 0.")
                weight = 0.0
            exam = cls(
                name=name,
                abrev=abrev,
                weight=weight,
                period=period,
                week=week
            )
            exams.append(exam)
        return exams
        return exams

# Utils
def parse_bullet_list(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\uf0b7•]", text) if item.strip()]

def weeks_to_dates(period: str, week1: int, week2: Optional[int]=None) -> tuple[date, date]:
    """Convierte un rango de semanas en fechas de inicio y fin."""
    if not isinstance(week1, int):
        raise ValueError("week1 must be an integer.")
    if not isinstance(week2, Optional[int]):
        raise ValueError("week2 must be an integer or None.")
    start_date = config.start_date(period) + timedelta(weeks=week1-1)
    if week2:
        if week1 > week2:
            raise ValueError("Rango de semanas inválido: la semana inicial no puede ser mayor que la semana final.")
        end_date = config.end_date(period) + timedelta(weeks=week2-1)
    else:
        end_date = start_date + timedelta(days=5)  # Por defecto, una semana dura 6 días hábiles
    return start_date, end_date

#ETL
def extract(directory: str) -> list[SyllabusRaw]:
    """Recorrer subdirectorios, encontrar PDFs de sílabos, leerlos en raw."""
    syllabi_raw = []
    try:
        syllabi_path = SyllabusRaw.find_syllabi(directory) 
        print(f'Extracting syllabi from {len(syllabi_path)} PDF files in "{directory}"')
        for pdfpath in syllabi_path:
            raw = SyllabusRaw.from_pdf(pdfpath)
            syllabi_raw.append(raw)
            print(f'File extracted: "{raw.filename}"')
    except Exception as e:
        print(f'Error extracting syllabi: {e}')
    return syllabi_raw

def transform(syllabi: list[SyllabusRaw]) -> list[Course]:
    courses = []
    print(f'Transforming {len(syllabi)} syllabi into structured Course data')
    try:
        for syllabus in syllabi:
            course = Course.from_raw(syllabus)
            courses.append(course)
            print(f'Course transformed: "{course}"')
    except Exception as e:
        print(f'Error transforming syllabi: {e}')
    return courses

# Guardar los cursos en archivos JSON. Uno por curso
def load(courses: list[Course], dest_dir: str='') -> list[str]:
    os.makedirs(dest_dir, exist_ok=True)
    paths = []
    print(f'Loading {len(courses)} courses into JSON files in "{dest_dir}"')
    for course in courses:
        try:
            path = course.to_json(dest_dir)
            paths.append(path)
            print(f'Course saved to JSON: "{os.path.basename(path)}"')
        except Exception as e:
            print(f'Error saving course "{course}": {e}')
    return paths
    

cwd = os.getcwd()
syllabi_raw = extract(cwd)

courses = transform(syllabi_raw)

loaded_paths = load(courses, os.path.join(cwd, 'cursos_json'))

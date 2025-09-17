"""
Orquestador del pipeline ETL y configuración
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
from etl_domain import Course, CourseMetadata
from etl_application import PDFExtractor, SyllabusParser, Repository
import logging

class ETLPipeline:
    def __init__(self, extractor: PDFExtractor, parser: SyllabusParser, repository: Repository, logger: Optional[logging.Logger] = None):
        self.extractor = extractor
        self.parser = parser
        self.repository = repository
        self.logger = logger or logging.getLogger(__name__)

    def process_syllabus(self, filepath: Path) -> Optional[Course]:
        try:
            self.logger.info(f"Extracting: {filepath.name}")
            text = self.extractor.extract_text(filepath)
            tables = self.extractor.extract_tables(filepath)
            metadata = self.parser.parse_metadata(filepath.name)
            content = self.parser.parse_content(text, tables)
            course = self._build_course(metadata, content)
            self.repository.save(course)
            self.logger.info(f"Saved course: {course.metadata.course_id}")
            return course
        except Exception as e:
            self.logger.error(f"Error processing {filepath}: {e}")
            return None

    def process_directory(self, directory: Path) -> List[Course]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        pdf_files = list(directory.rglob("UG-*_1A*-*.pdf"))
        self.logger.info(f"Found {len(pdf_files)} PDF files")
        processed_courses = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.process_syllabus, pdf): pdf for pdf in pdf_files}
            for future in as_completed(futures):
                if course := future.result():
                    processed_courses.append(course)
        
        # Save all courses in a single file
        if processed_courses:
            self._save_all_courses(processed_courses)
            
        # Generate weekly calendar
        self._generate_weekly_calendar(processed_courses)
        
        return processed_courses
    
    def _save_all_courses(self, courses: List[Course]) -> None:
        """Save all courses in a single JSON file"""
        import json
        all_courses_data = [self.repository._to_dict(course) for course in courses]
        all_courses_path = self.repository.base_path / 'all_courses.json'
        
        with open(all_courses_path, 'w', encoding='utf-8') as f:
            json.dump(all_courses_data, f, ensure_ascii=False, indent=4)
        
        self.logger.info(f'All courses saved to: {all_courses_path}')
    
    def _generate_weekly_calendar(self, courses: List[Course]) -> None:
        """Generate a weekly calendar as PDF showing all assessments across courses"""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        # Collect all assessments with course info
        weekly_assessments = {}
        
        for course in courses:
            course_abbrev = course.metadata.course_id
            for assessment in course.assessments:
                week = assessment.week
                if week not in weekly_assessments:
                    weekly_assessments[week] = []
                
                assessment_text = f"•{course_abbrev}: {assessment.name} ({assessment.weight}%)"
                weekly_assessments[week].append(assessment_text)
        
        # Create PDF
        calendar_path = self.repository.base_path / 'weekly_calendar.pdf'
        doc = SimpleDocTemplate(str(calendar_path), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        story.append(Paragraph("Calendario Semanal de Evaluaciones", title_style))
        story.append(Spacer(1, 12))
        
        # Course list header
        story.append(Paragraph("Cursos:", styles['Heading2']))
        story.append(Spacer(1, 6))
        
        # Add course list
        for course in courses:
            course_abbrev = course.metadata.course_id
            course_line = f"•{course_abbrev}: {course.name}"
            story.append(Paragraph(course_line, styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Table header
        story.append(Paragraph("Cronograma de Evaluaciones por Semana:", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Prepare table data
        table_data = [['Semana', 'Contenido']]  # Header
        
        for week in sorted(weekly_assessments.keys()):
            content_lines = weekly_assessments[week]
            content_text = '\n'.join(content_lines)  # Use newline instead of <br/>
            table_data.append([str(week), content_text])
        
        # Create table
        if len(table_data) > 1:  # If there's data beyond header
            table = Table(table_data, colWidths=[1*inch, 5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No se encontraron evaluaciones programadas.", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        self.logger.info(f'Weekly calendar PDF saved to: {calendar_path}')

    def _build_course(self, metadata: CourseMetadata, content: Dict) -> Course:
        """Build Course object from metadata and parsed content"""
        from etl_domain import Unit, Assessment
        
        # Parse units from table
        units = self._parse_units_from_table(content.get('units_table', []), metadata.period)
        
        # Parse assessments from table  
        assessments = self._parse_assessments_from_table(content.get('assessments_table', []), metadata.period)
        
        return Course(
            metadata=metadata,
            name=content.get("name", ""),
            faculty=content.get("faculty", []),
            credits=content.get("credits", 0),
            total_weeks=content.get("weeks", 16),
            areas=content.get("areas", []),
            units=units,
            assessments=assessments
        )
    
    def _parse_units_from_table(self, table: List[List[str]], period: str) -> List:
        """Parse units from raw table data"""
        from etl_domain import Unit
        import re
        
        if not table:
            return []
            
        def clean_table_structure(table: List[List[str]]) -> List[List[str]]:
            """Clean table by removing empty rows and combining split rows"""
            table = table.copy()
            
            def join_with_previous(index: int):
                if index <= 0 or index >= len(table):
                    return
                prev_row = table[index-1]
                curr_row = table[index]
                new_row = [
                    (prev.strip() + ' ' + curr.strip()).strip() if curr else prev
                    for prev, curr in zip(prev_row, curr_row)
                ]
                if len(curr_row) > len(prev_row):
                    new_row.extend(curr_row[len(prev_row):])
                table[index-1] = new_row
                del table[index]
            
            i = 0
            while i < len(table):
                if not table[i][0].startswith("Unidad n."):
                    raise ValueError(f"Invalid unit title format: {table[i][0]}")
                i += 1
                if i < len(table) and not table[i][0].startswith("COMPETENCIA (S):"):
                    raise ValueError(f"Invalid competition format: {table[i][0]}")
                i += 1
                while i < len(table) and not table[i][0].startswith("LOGRO DE LA UNIDAD:"):
                    if i == len(table)-1:
                        raise ValueError(f"Invalid achievement format: {table[i][0]}")
                    join_with_previous(i)
                i += 1
                while i < len(table) and not table[i][0].startswith("SEMANA"):
                    if i == len(table)-1:
                        raise ValueError(f"Invalid header format: {table[i]}")
                    join_with_previous(i)
                i += 1
                if i < len(table) and not table[i][0].startswith("Semana"):
                    raise ValueError(f"Invalid week format: {table[i][0] if i < len(table) else 'EOF'}")
                i += 1
                while i < len(table) and not table[i][0].startswith("Unidad n."):
                    join_with_previous(i)
            return table
        
        def parse_title(line: str) -> tuple[int, str]:
            match = re.match(r"^Unidad n\. (?P<numero>\d+): (?P<titulo>.+)", line)
            if match:
                number = int(match.group("numero"))
                title = match.group("titulo")
                return number, title
            raise ValueError(f"Invalid unit title format: {line}")

        def parse_week_row(row: List[str]) -> tuple:
            row = [field.replace("\n", " ") for field in row]
            parsed = re.match(r"Semana (?P<semana1>[\d,\s-]+)\s*-\s*(?P<semana2>[\d,\s-]+)", row[0])
            if parsed:
                week1 = int(parsed.group("semana1"))
                week2 = int(parsed.group("semana2"))
            else:
                raise ValueError(f"Invalid week format: {row[0]}")
            
            syllabus = self._parse_bullet_list(row[1]) if len(row) > 1 else []
            activities = self._parse_bullet_list(row[2]) if len(row) > 2 else []
            exams = self._parse_bullet_list(row[3]) if len(row) > 3 else []
            bibliography = self._parse_bullet_list(row[4]) if len(row) > 4 else []
            
            return week1, week2, syllabus, activities, exams, bibliography

        units = []
        table = clean_table_structure(table)
        
        for i in range(0, len(table), 5):
            if i >= len(table):
                break
            number, title = parse_title(table[i][0])
            achievement = table[i+2][0].replace("LOGRO DE LA UNIDAD:", "").strip()
            week1, week2, syllabus, activities, exams, bibliography = parse_week_row(table[i+4])
            
            units.append(Unit(
                number=number,
                title=title,
                achievement=achievement,
                week_range=(week1, week2),
                syllabus=syllabus,
                activities=activities
            ))
        
        return units
    
    def _parse_assessments_from_table(self, table: List[List[str]], period: str) -> List:
        """Parse assessments from raw table data"""
        from etl_domain import Assessment
        
        if not table:
            return []
            
        header = ['TIPO', 'COMPETENCIA', 'PESO', 'SEMANA', 'OBSERVACIÓN', 'RECUPERABLE']
        assessments = []
        
        for row in table:
            if row == header:
                continue
            
            row = [field.replace('\n', ' ').strip() for field in row]
            if len(row) < 4:
                continue
                
            name, code = row[0].split('-', 1) if '-' in row[0] else (row[0], '')
            code = code.strip()
            
            try:
                week = int(row[3])
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid week value '{row[3]}' in exam '{name}'. Skipping.")
                continue
                
            try:
                weight = float(row[2].rstrip('%'))
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid weight value '{row[2]}' in exam '{name}'. Setting to 0.")
                weight = 0.0
            
            is_recoverable = len(row) > 5 and 'sí' in row[5].lower()
            
            assessments.append(Assessment(
                name=name,
                code=code,
                weight=weight,
                week=week,
                is_recoverable=is_recoverable
            ))
        
        return assessments
    
    def _parse_bullet_list(self, text: str) -> List[str]:
        """Parse bullet list from text"""
        import re
        return [item.strip() for item in re.split(r"[\uf0b7•]", text) if item.strip()]

class PipelineFactory:
    @staticmethod
    def create_default_pipeline(output_dir: Path) -> ETLPipeline:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        from etl_infrastructure import PDFPlumberExtractor, UPCSyllabusParser, JSONRepository
        return ETLPipeline(
            extractor=PDFPlumberExtractor(),
            parser=UPCSyllabusParser(),
            repository=JSONRepository(output_dir),
            logger=logging.getLogger("ETL")
        )

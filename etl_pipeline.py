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
        pdf_files = list(directory.rglob("*.pdf"))
        self.logger.info(f"Found {len(pdf_files)} PDF files")
        processed_courses = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.process_syllabus, pdf): pdf for pdf in pdf_files}
            for future in as_completed(futures):
                if course := future.result():
                    processed_courses.append(course)
        return processed_courses

    def _build_course(self, metadata: CourseMetadata, content: Dict) -> Course:
        # Implementación real
        return Course(
            metadata=metadata,
            name=content.get("name", ""),
            faculty=content.get("faculty", []),
            credits=content.get("credits", 0),
            total_weeks=content.get("weeks", 16),
            areas=content.get("areas", []),
            units=[],
            assessments=[]
        )

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

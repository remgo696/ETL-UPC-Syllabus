"""
Entidades de dominio y value objects para el ETL de sílabos UPC
"""
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass(frozen=True)
class CourseMetadata:
    course_id: str
    nrc: str
    period: str

@dataclass
class Unit:
    number: int
    title: str
    achievement: str
    week_range: Tuple[int, int]
    syllabus: List[str] = field(default_factory=list)
    activities: List[str] = field(default_factory=list)

@dataclass
class Assessment:
    name: str
    code: str
    weight: float
    week: int
    is_recoverable: bool = False

@dataclass
class Course:
    metadata: CourseMetadata
    name: str
    faculty: List[str]
    credits: int
    total_weeks: int
    areas: List[str]
    units: List[Unit] = field(default_factory=list)
    assessments: List[Assessment] = field(default_factory=list)

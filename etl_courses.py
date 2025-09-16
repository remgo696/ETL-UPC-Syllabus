"""
Punto de entrada del ETL modular para sílabos UPC
"""
from pathlib import Path
import argparse
from etl_pipeline import PipelineFactory

def main():
    parser = argparse.ArgumentParser(description="ETL Pipeline for UPC Syllabi")
    parser.add_argument("input_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument("output_dir", type=Path, help="Output directory for JSON files")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    pipeline = PipelineFactory.create_default_pipeline(args.output_dir)
    courses = pipeline.process_directory(args.input_dir)
    print(f"Processed {len(courses)} courses successfully")

if __name__ == "__main__":
    main()
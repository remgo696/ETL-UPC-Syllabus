# ETL-UPC-Syllabus

Este proyecto extrae información estructurada de los sílabos en PDF de cursos de la Universidad Peruana de Ciencias Aplicadas (UPC) y la guarda en archivos JSON para su posterior análisis o uso.

## ¿Qué hace este proyecto?
- Busca automáticamente los archivos PDF de sílabos en las carpetas de cursos.
- Extrae datos relevantes (nombre, código, NRC, unidades, evaluaciones, etc.).
- Convierte la información a un formato estructurado (JSON).
- Guarda un archivo JSON por curso y un archivo con todos los cursos juntos.
- Genera un calendario semanal en PDF con todas las evaluaciones programadas.

## Requisitos previos
- **Python 3.8 o superior**
- **pipenv** (gestor de entornos y dependencias)

## Instalación de dependencias
1. Abre la terminal (cmd o PowerShell) en la carpeta del proyecto.
2. Instala pipenv si no lo tienes:
   ```cmd
   pip install pipenv
   ```
3. Instala las dependencias del proyecto:
   ```cmd
   pipenv install
   ```
   Esto instalará automáticamente todas las librerías necesarias (`pdfplumber`, `reportlab`).

## Estructura esperada de carpetas
```
proyecto/
├── etl_courses.py
├── config.json
├── Pipfile
├── raw/                          # Carpeta de entrada
│   ├── 1AEL0244 Análisis de Circuitos Eléctricos 2/
│   │   └── UG-202520_1AEL0244-8281.pdf
│   └── ...
└── data/                         # Carpeta de salida (se crea automáticamente)
    ├── {curso}-{nrc}.json
    ├── all_courses.json
    └── weekly_calendar.pdf
```


## Cómo ejecutar el script
1. Asegúrate de que los archivos PDF de los sílabos estén en las carpetas correspondientes.
2. Abre la terminal en la carpeta del proyecto.
3. Activa el entorno virtual:
   ```cmd
   pipenv shell
   ```
4. Ejecuta el script especificando carpeta de entrada y salida:
   ```cmd
   python etl_courses.py raw data
   ```
   - `raw`: Carpeta donde están los archivos PDF de sílabos
   - `data`: Carpeta donde se guardarán los resultados

## Archivos generados
Al finalizar, encontrarás los siguientes archivos en la carpeta de salida:
- **Archivos individuales:** Un archivo JSON por curso (`{nombre_curso}-{nrc}.json`)
- **Archivo consolidado:** `all_courses.json` con todos los cursos juntos
- **Calendario PDF:** `weekly_calendar.pdf` con cronograma semanal de evaluaciones

## Notas adicionales
- Si agregas nuevos sílabos, vuelve a ejecutar el script para actualizar los archivos JSON.
- El archivo `config.json` define las fechas de inicio y fin del periodo académico. Modifícalo si cambian los periodos.

## Contacto
Para dudas o sugerencias, contacta al responsable del proyecto o abre un issue en el repositorio.

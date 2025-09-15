# ETL-UPC-Syllabus

Este proyecto extrae información estructurada de los sílabos en PDF de cursos de la Universidad Peruana de Ciencias Aplicadas (UPC) y la guarda en archivos JSON para su posterior análisis o uso.

## ¿Qué hace este proyecto?
- Busca automáticamente los archivos PDF de sílabos en las carpetas de cursos.
- Extrae datos relevantes (nombre, código, NRC, unidades, evaluaciones, etc.).
- Convierte la información a un formato estructurado (JSON).
- Guarda un archivo JSON por curso y un archivo con todos los cursos juntos.

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
   Esto instalará automáticamente todas las librerías necesarias (por ejemplo, `pdfplumber`).

## Estructura esperada de carpetas
```
proyecto/
├── etl_courses.py
├── config.json
├── Pipfile
├── 1AEL0244 Análisis de Circuitos Eléctricos 2/
│   └── UG-202520_1AEL0244-8281.pdf
├── ...
```

## Cómo ejecutar el script
1. Asegúrate de que los archivos PDF de los sílabos estén en las carpetas correspondientes.
2. Abre la terminal en la carpeta del proyecto.
3. Activa el entorno virtual:
   ```cmd
   pipenv shell
   ```
4. Ejecuta el script:
   ```cmd
   python etl_courses.py
   ```
5. Al finalizar, encontrarás los archivos JSON en la carpeta `cursos_json`.
   - Un archivo por curso.
   - Un archivo `all_courses.json` con todos los cursos juntos.

## Notas adicionales
- Si agregas nuevos sílabos, vuelve a ejecutar el script para actualizar los archivos JSON.
- El archivo `config.json` define las fechas de inicio y fin del periodo académico. Modifícalo si cambian los periodos.

## Contacto
Para dudas o sugerencias, contacta al responsable del proyecto o abre un issue en el repositorio.

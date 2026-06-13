# PROYECTO: informes-cev-minvu-db

## 1. CONTEXTO DEL NEGOCIO

El Ministerio de Vivienda y Urbanismo (MINVU) de Chile publica evaluaciones de eficiencia energética de viviendas en el portal público:
`http://calificacionenergeticaweb.minvu.cl/Publico/BusquedaVivienda.aspx`

Cada evaluación genera un **Informe CEV v2** (PDF de 7 páginas) con datos detallados: demanda energética, envolvente térmica, consumo, temperaturas horarias, y datos del evaluador. Existen ~156.000+ evaluaciones históricas, distribuidas en 16 regiones y 348 comunas.

**Dos tipos de evaluación:**
- Tipo 1: Precalificación Energética (pre-construcción)
- Tipo 2: Calificación Energética (post-construcción)

**Escala de eficiencia:**
| Letra | Ahorro (%) |
|-------|-----------|
| A+ | > 85% |
| A | 70-85% |
| B | 55-70% |
| C | 40-55% |
| D | 20-40% |
| E | 0-20% |
| F | -10% a 0% |
| G | < -35% |

---

## 2. SITUACIÓN ACTUAL — PROYECTOS LEGACY

Existen 4 proyectos legacy (implementaciones previas del mismo scraping):

| Proyecto | Ruta | Estado |
|----------|------|--------|
| **cev-database-scraper** | `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-database-scraper/` | 1ra gen: ETL monolítico → CSVs → PostgreSQL. Sin PDF. |
| **cev-data-lake** | `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-data-lake/` | 2da gen: Jupyter notebooks, scraping HTML+PDF, SQLite, NoCodeBackend. |
| **Informe-CEV-v2-pdf-scraper** | `/mnt/g/My Drive/R2F-EES/Development/Informe-CEV-v2-pdf-scraper/` | App Streamlit para extraer datos de PDFs CEV v2 (subida manual). Tiene el código de extracción más refinado con tests. |
| **datacev-chile** | `/mnt/g/My Drive/R2F-EES/Development/datacev-chile/` | 3ra gen: Paquete Python con SQLModel, scraping async, pipeline productor/consumidor, OCR. |

---

## 3. LO QUE QUEREMOS CONSTRUIR

Un sistema **ELT/ETL** de datos que:

### a) Scraping del Portal MINVU
- Scrapear el listado de evaluaciones disponibles por comuna (HTML del portal ASP.NET WebForms)
- Descargar los PDFs individuales (Informe CEV v2, 7 páginas)
- **Debe soportar descargas paralelas** (múltiples conexiones HTTP simultáneas)
- **Dos flujos independientes pero complementarios:**
  1. Obtener el directorio completo de informes disponibles (metadatos desde HTML)
  2. Descargar y extraer los PDFs individuales

### b) Extracción de Datos del PDF (7 páginas)
- Páginas 1-5 y 7: Extracción por coordenadas (como en el código legacy) usando PyMuPDF
- **Página 6 (OCR):** Contiene perfiles de temperatura horaria (24h) para 4 meses (enero, abril, julio, octubre). Son números pequeños en gráficos hechos en Excel. Algunos informes muestran 3 perfiles, otros 2. Las coordenadas cambian según la cantidad de perfiles.
- **Verificación visual de coordenadas:** El sistema debe poder generar un PDF con los rectángulos de extracción dibujados (contours) para que el usuario verifique visualmente que las coordenadas capturan el texto completo. Ver `draw_all_pages_rectangles()` en el scraper de Informe-CEV-v2-pdf-scraper.

### c) Normalización y Tipado de Datos
- Todo lo que scrapea llega como string. Se debe normalizar a tipos correctos:
  - `float` (con comas decimales chilenas → puntos)
  - `int` (IDs, horas, meses)
  - `date` (fechas en formato chileno)
  - `text` (descripciones, nombres)
- Definir esquema de datos completo con tipos

### d) Almacenamiento
- Base de datos principal (a definir)
- **Espejo en NoCodeBackend.com:** Tiene licencia lifetime. El espejo debe ser unidireccional (app → NoCodeBackend) para que agentes Claude Code/Codex/OpenCode puedan consultar los datos vía REST/MCP sin acceso SSH.
  - **Referencia de implementación:** Ver `/home/roruizf/projects/sgip-system/src/integration/nocode_mirror.py` — usa MCP para DDL (CREATE TABLE) y REST API para CRUD, con full-replace o incremental push.
  - La estructura del espejo debe definirse con el equipo.

### e) OCR para Página 6 — PERFILES DE TEMPERATURA VARIABLES

La página 6 contiene perfiles de temperatura horaria (24h) para 4 meses (enero, abril, julio, octubre). Los datos son **números pequeños incrustados en gráficos hechos en Excel**. Hay dos variantes del informe que cambian las coordenadas:

- **2 filas de temperatura** (2 perfiles: exterior e interior). Ejemplo:
  `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-data-lake/data/raw/3_evals_reports/pdf_files/10/10_6_1_7222f509-d377-54bd-b0fc-329af50ecedd.pdf`

- **3 filas de temperatura** (3 perfiles: exterior, interior, y uno adicional). Ejemplo:
  `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-data-lake/data/raw/3_evals_reports/pdf_files/3/3_39_2_9f2c24ce-0e69-5740-8ee7-f2b5e7844073.pdf`

El sistema debe detectar automáticamente qué variante es y ajustar las coordenadas de extracción/OCR.

**Herramienta disponible:** `/home/roruizf/projects/doc2md/` — conversor de PDFs a Markdown con OCR (Tesseract + Docling). Se puede usar como librería Python: `from doc2md import convert`. Doc2md fue creado por el mismo equipo.

### f) REUTILIZAR PDFS EXISTENTES EN GOOGLE DRIVE (opcional — tú decides)

Existe una carpeta en Google Drive con MILES de PDFs ya descargados:
`/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-data-lake/data/raw/3_evals_reports/pdf_files/`

Organizada por región (ej: `10/`, `3/`, etc.). Puedes:

- **Opción A:** Usar estos PDFs desde Google Drive para la extracción inicial, evitando saturar el servidor MINVU con ~156K descargas. El acceso debe hacerse **desde la VPS, dentro del container Docker**. Para ello existe `gws-cli` (Google Workspace CLI) en `/home/linuxbrew/.linuxbrew/bin/gws`. Investiga si se puede integrar dentro del container para autenticar y descargar los PDFs bajo demanda.
- **Opción B:** Ignorarlos y descargar todo desde cero desde el servidor MINVU.
- **IMPORTANTE:** Los archivos locales en `/mnt/c/Users/rober/...` NO están disponibles desde la VPS. Solo están los PDFs en Google Drive. Si optas por Opción A, el container debe conectarse a Google Drive directamente.
- **Tú decides cuál es mejor** según: integridad de los datos, riesgo de rate-limiting del servidor MINVU, factibilidad técnica de gws-cli en Docker, y tiempo total estimado.

### g) Limpieza de PDFs
- Los PDFs descargados deben eliminarse después de extraerlos para no ocupar espacio en disco.
- Política: extraer → borrar. Si falla, reintentar N veces y luego borrar igual. Cleanup global periódico de PDFs con >N días.

### h) Resiliencia y Operación 24/7
- El sistema debe correr 24/7 en una VPS via Docker (Zeabur.com)
- **Fase inicial:** Scrapeo masivo de todos los informes (~156K)
- **Fase estable:** Un scrape diario incremental (solo nuevos informes)
- Debe ser tolerante a fallos: retry con backoff, dead letter queue, logging estructurado
- Debe tener health checks: `GET /health`, `GET /health/db`, `GET /health/last-scrape`

### i) Base de datos existente
- Existe una BD SQLite en los proyectos legacy con datos incompletos (sin OCR, sin página 6). Evaluar si se puede importar al nuevo sistema y enriquecer.

### j) Alcance: Solo Informes CEV v2 (7 páginas)
- Los informes v1 (4 páginas) están fuera del alcance por ahora. El sistema debe detectar v2 y saltarse v1.
- En un futuro podría implementarse v1, pero no ahora.

---

## 4. DECISIONES QUE DEBES TOMAR TÚ (CLAUDE FABLE)

Como arquitecto/implementador, tú debes proponer y decidir:

1. **Arquitectura general:** ¿Un solo servicio o múltiples? ¿Qué framework web?
2. **Base de datos:** ¿PostgreSQL? ¿SQLite? ¿Cuál se adapta mejor a Zeabur + NoCodeBackend?
3. **Orquestación:** ¿APScheduler embebido? ¿Prefect? ¿Cron-job.org externo? ¿Otro? Lo mas simple posible.
4. **Librerías de scraping:** ¿httpx? ¿aiohttp? ¿requests?
5. **Diseño de BD:** Debes investigar la información del Informe CEV v2 usando NotebookLM (ver sección 6) y también la BD actual para proponer el esquema.
6. **Estrategia de OCR:** ¿Usar doc2md directo? ¿Solo para página 6? ¿Extraer página 6 como PDF separado primero?
7. **Estrategia de sincronización con NoCodeBackend:** ¿Incremental? ¿Full-replace? ¿Batch?
8. **Estructura del proyecto y naming:** Propón la estructura de directorios, módulos, etc.
9. **Estrategia de importación de BD legacy.**
10. **Nombre del proyecto:** `informes-cev-minvu-db` (ya definido). La estructura del repositorio y el paquete Python deben reflejar este nombre.

---

## 5. LO QUE NO DEBES CAMBIAR (REQUISITOS FIRMES)

- OCR vía doc2md (debe integrarse)
- NoCodeBackend como espejo (usar patrón de sgip-system)
- Docker para deploy en Zeabur.com
- PDF cleanup automático
- Health checks HTTP
- Coordenadas verificables visualmente (draw_all_pages_rectangles)
- Escala de eficiencia A+ a G
- Múltiples descargas HTTP paralelas
- Dos flujos separados: directorio de informes + descarga de PDFs

---

## 6. FUENTES QUE DEBES INVESTIGAR

### Proyectos legacy (código funcional):

#### datacev-chile (3ra gen)
**Ruta:** `/mnt/g/My Drive/R2F-EES/Development/datacev-chile/`
- Modelo de datos mas completo (SQLModel en `src/database/models.py`)
- Pipeline productor/consumidor en `src/pipelines/`
- PDF parser con OCR en `src/scraping/pdf_parser.py`

#### Informe-CEV-v2-pdf-scraper (extracción refinada)
**Ruta:** `/mnt/g/My Drive/R2F-EES/Development/Informe-CEV-v2-pdf-scraper/`
- `scraping_functions.py` — extracción por coordenadas + dibujo de rectángulos + OCR página 6
- `get_page_coordinates()` — todas las coordenadas para las 7 páginas
- `draw_all_pages_rectangles()` — verificación visual de coordenadas
- Tests en `tests/`

#### cev-data-lake (2da gen)
**Ruta:** `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-data-lake/`
- `utils/pdf_functs.py` — extractores por página (página 1 a 7)
- `utils/html_functs.py` — parser de HTML del portal ASP.NET
- `utils/requests_functs.py` — construcción de form data ASP.NET
- `ingestion/ingest_to_nocode_backend.py` — sync con NoCodeBackend
- PDFs de ejemplo en `data/raw/3_evals_reports/pdf_files/`

#### cev-database-scraper (1ra gen)
**Ruta:** `/mnt/c/Users/rober/OneDrive/8_DEVELOPMENT/cev-database-scraper/`
- `pipeline/extract.py` — scraping del portal MINVU
- `pipeline/transform.py` — limpieza y normalización
- `pipeline/load.py` — carga a PostgreSQL
- `xpath.txt` — expresiones XPath para el portal

### Herramientas disponibles:

#### doc2md (OCR)
**Ruta:** `/home/roruizf/projects/doc2md/`
- API Python: `from doc2md import convert`
- Usa Docling o Tesseract directo

#### sgip-system (referencia NoCodeBackend)
**Ruta:** `/home/roruizf/projects/sgip-system/`
- `src/integration/nocode_mirror.py` — clase NocodeMirror (MCP + REST)
- `src/jobs/nocode_sync.py` — job de sincronización diaria
- **Copiar este patrón exacto para el espejo NoCodeBackend**

#### gws-cli (Google Workspace CLI)
**Ruta:** `/home/linuxbrew/.linuxbrew/bin/gws`
- Para acceder a PDFs existentes en Google Drive desde la VPS
- Investiga y decide si es viable

#### NotebookLM (para entender el dominio CEV)
**CLI en:** `/home/roruizf/tools/notebooklm/.venv/bin/notebooklm`
- Autenticado como roberto@r2f.solutions
- Crea un notebook con fuentes sobre la CEV y haz preguntas sobre el formato del informe v2
- Úsalo para entender qué datos contiene cada página y cómo se relacionan

### Documentación del análisis previo (en Google Drive, disponible como referencia):
- `/mnt/g/My Drive/R2F-EES/Development/cev-nexus/docs/PROJECT_CONTEXT.md`
- `/mnt/g/My Drive/R2F-EES/Development/cev-nexus/docs/ARCHITECTURE.md` (OBSOLETA — solo para entender decisiones pasadas)
- `/mnt/g/My Drive/R2F-EES/Development/cev-nexus/docs/DATA_DICTIONARY.md`

---

## 7. PROCESO DE TRABAJO

1. **Analiza y audita.** Lee todas las fuentes. Entiende el dominio, el código legacy, las herramientas y el portal MINVU.
2. **Propón una arquitectura.** Antes de escribir código, presenta un plan detallado con:
   - Arquitectura propuesta (diagrama)
   - Stack tecnológico
   - Diseño de BD (tablas, columnas, tipos, relaciones)
   - Estructura del proyecto
   - Flujo de datos (ELT)
   - Estrategia de deployment
   - Cualquier duda, pregúntala
3. **Ejecuta.** Una vez aprobado el plan, implementa.

---

## 8. PREGUNTAS QUE DEBES RESPONDER EN TU PLAN

- ¿Qué base de datos usamos y por qué?
- ¿Cómo orquestamos los jobs sin Kestra?
- ¿Integramos doc2md como librería o como CLI? ¿Para toda la página 6 o para sub-áreas?
- ¿Cómo manejamos las coordenadas variables de página 6 (2 vs 3 perfiles)?
- ¿Cómo detectamos automáticamente 2 vs 3 perfiles?
- ¿Conviene reutilizar los PDFs existentes en Google Drive o mejor descarga fresca?
- Si se reutilizan, ¿cómo se accede desde la VPS (gws-cli vs montar Google Drive)?
- ¿Cómo hacemos el sync con NoCodeBackend: incremental o full-replace?
- ¿Importamos la BD legacy existente o empezamos de cero?
- ¿Cómo estructuramos los health checks para Zeabur?
- **Nombre del proyecto:** `informes-cev-minvu-db` — está decidido.

---

## 9. NOTAS ADICIONALES

- El nombre del proyecto es **informes-cev-minvu-db**.
- Accesible por agentes Claude Code / Codex / OpenCode a través del espejo de NoCodeBackend.
- **Prioriza SIMPLICIDAD sobre complejidad arquitectónica.** Menos servicios = menos puntos de falla.
- Deployment en **Zeabur.com** via Docker. Zeabur NO tiene cron nativo.
- Dos etapas: (1) carga masiva inicial (~156K), (2) ejecución diaria incremental.
- Si algo no está claro, PREGUNTA antes de asumir.

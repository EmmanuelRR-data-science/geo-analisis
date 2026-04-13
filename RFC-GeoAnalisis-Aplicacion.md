# RFC: Estandar de Arquitectura y Evolucion de la Aplicacion GeoAnalisis

- **Author(s):** Emmanuel Ramirez Romero
- **Status:** Propuesta
- **Ultima actualizacion:** 2026-04-13

## Links

- Repositorio: `GeoAnalisis`
- Plantilla base: `rfc-template.md`
- Fuente de especificaciones: `.kiro/specs/*`

## Goals

- Consolidar en un solo RFC la vision funcional y tecnica derivada de `business-viability-map`, `docker-postgres`, `advanced-filters-layers`, `strategic-recommendations` y `multi-radius-environment-analysis`.
- Formalizar una arquitectura por capas para reducir acoplamiento en `app/main.py` y facilitar evolucion incremental.
- Estandarizar resiliencia operativa frente a fallas de Google Places, DENUE y Groq con degradacion controlada.
- Definir trazabilidad de requisitos -> diseño -> tareas -> metricas.
- Priorizar cierre de brechas de calidad (tests de propiedades, observabilidad y persistencia de analisis).

## Non-Goals

- Reescritura total del frontend o cambio de stack (Leaflet/FastAPI se mantienen).
- Cambio de proveedores (Groq, Google Places, DENUE) en esta fase.
- Implementacion de autenticacion multiusuario o control de acceso granular.
- Despliegue multi-region.

## Background

GeoAnalisis ya opera como sistema end-to-end con:

- analisis por zona o coordenadas,
- consolidacion multi-fuente (Google Places + DENUE, Overture como fuente futura),
- clasificacion con LLM y fallback local,
- scoring de viabilidad,
- recomendaciones generales y estrategicas,
- analisis multi-radio (1 km, 3 km, 5 km),
- variables AGEB ampliadas y variables derivadas de entorno,
- exportaciones PDF y HTML autonomo,
- ejecucion dockerizada con PostgreSQL/PostGIS.

La documentacion de `requirements.md`, `design.md` y `tasks.md` muestra que la mayor parte del alcance funcional esta implementada, pero persisten deudas en pruebas basadas en propiedades y en formalizacion de observabilidad/contratos.

## Overview

Arquitectura objetivo (evolucionaria, no disruptiva):

1. **API Layer**: validacion de entrada, contrato de errores, versionado y control de compatibilidad.
2. **Orchestration Layer**: pipeline de analisis y paralelismo controlado.
3. **Domain Layer**: interpretacion, clasificacion, scoring, recomendaciones y calculo de variables de entorno.
4. **Integration Layer**: clientes externos con politicas unificadas de timeout/reintento/degradacion.
5. **Data Layer**: PostgreSQL/PostGIS para AGEB + almacenamiento de analisis y cache.
6. **Presentation/Export Layer**: frontend Leaflet y exportadores PDF/HTML con contenido completo.

## Detailed Design

### Solucion

#### 1) Alcance funcional consolidado

- **Analisis base**: formulario de negocio + zona/coords, busqueda de negocios, clasificacion, score y recomendacion.
- **Infraestructura**: Docker + `postgis/postgis:16-3.4`, healthcheck DB y AGEBReader sobre SQLAlchemy.
- **Filtros avanzados**: filtros SCIAN y Google Places (aliados/competidores), radio configurable, capas AGEB, export HTML interactivo.
- **Estrategia comercial**: recomendaciones estrategicas (3-7) con fallback por reglas.
- **Analisis espacial avanzado**: resultados multi-radio, variables derivadas (`poi_density`, `commercial_activity_index`, `sector_concentration`) e indicadores AGEB extendidos.

#### 2) Contratos API y datos

- Mantener endpoints actuales y preparar versionado `/api/v1`.
- Contratos clave ya activos:
  - `AnalysisResult` con `strategic_recommendations` y `multi_radius_results`.
  - `AGEBData` con `extended_indicators`.
  - `Business` enriquecido con `google_price_level`, `google_types`, `google_reviews`, `google_editorial_summary`.
- Estandarizar `APIError` para todos los endpoints con `error`, `message`, `details`, `warnings`.

#### 3) Orquestacion

- Extraer gradualmente el flujo de `/api/analyze` a `AnalysisOrchestrator`.
- Pipeline objetivo:
  1. Validacion y normalizacion de entrada.
  2. Interpretacion de negocio.
  3. Busqueda principal + busquedas multi-radio en paralelo.
  4. Clasificacion y scoring.
  5. Recomendaciones general y estrategicas.
  6. Ensamble de respuesta y persistencia.
- Mantener `asyncio.gather(..., return_exceptions=True)` para degradacion parcial por radio/fuente.

#### 4) Resiliencia y timeouts

- Baseline documentado:
  - Groq: timeout corto + retries.
  - Google Places y DENUE: timeout/reintento con warnings.
  - Health DB: respuesta `ok`/`degraded` sin romper disponibilidad del endpoint.
- Politica objetivo:
  - fallo parcial no bloquea analisis completo,
  - warnings siempre propagados al cliente,
  - fallback determinista para clasificacion y recomendaciones.

#### 5) Persistencia y ciclo de vida

- Estado actual: AGEB persistido en PostgreSQL/PostGIS; resultados de analisis en memoria.
- Objetivo RFC:
  - persistir resultados de analisis (resumen + metadatos),
  - habilitar cache por combinacion (zona/coords + giro + radio + filtros),
  - definir politica de retencion y limpieza.

#### 6) Exportaciones y UX de decision

- PDF y HTML deben incluir:
  - resumen principal,
  - recomendaciones general y estrategicas,
  - comparativo multi-radio,
  - variables ampliadas de entorno.
- HTML exportado debe conservar interactividad de mapa y capas clave.

### Propuesta arquitectura

```
Cliente Web (Leaflet + panel analitico)
   |
FastAPI Router
   |
AnalysisOrchestrator
   |---- Domain Services (LLMService, AnalysisEngine, EnvironmentCalculator)
   |---- Data Aggregation (GooglePlacesClient, DENUEClient, OvertureClient*)
   |---- AGEBReader (PostgreSQL/PostGIS)
   |
Result Store + Cache (nuevo)
   |
ExportService (PDF / HTML autonomo)
```

\* Overture se mantiene como integracion futura en la practica.

## Consideraciones

- **Seguridad:** secretos fuera del repo, CORS restringido en produccion, no exponer detalles internos de excepcion.
- **Calidad de datos:** explicitar `data_completeness`, warnings por fuente y estado de fallback.
- **Performance:** paralelismo multi-radio y limites de latencia por proveedor externo.
- **Mantenibilidad:** reducir complejidad de `main.py` con orquestador y servicios de dominio puros.
- **Trazabilidad:** cada bloque funcional debe mapear a requisitos/documentos de `.kiro/specs`.

## Metricas

### Metricas tecnicas

- **p95 `/api/analyze`** <= 8 s con proveedores disponibles.
- **Disponibilidad API** >= 99.5% mensual.
- **Error rate por proveedor externo** < 5%.
- **Cobertura de pruebas de dominio** >= 80%.
- **Cobertura de propiedades criticas** >= 70% de propiedades definidas en specs.

### Metricas de producto/analisis

- **Completitud promedio por analisis** >= 0.75.
- **Analisis con recomendacion util (sin fallback total)** >= 85%.
- **Tiempo de exportacion PDF/HTML** <= 2 s post-analisis.
- **Consistencia multi-radio** sin incoherencias de conteos ni formulas.

## Plan de implementacion (fases)

1. **Fase 1 - Hardening de calidad**
   - Implementar suite pendiente de tests de propiedades y tests unitarios criticos.
   - Estandarizar mensajes de error y warnings en toda la API.
2. **Fase 2 - Refactor de orquestacion**
   - Introducir `AnalysisOrchestrator`.
   - Reducir logica procedural en `/api/analyze`.
3. **Fase 3 - Persistencia de resultados**
   - Persistir historico de analisis y cache.
   - Definir retencion, limpieza y versionado de algoritmo.
4. **Fase 4 - Observabilidad operativa**
   - Logs estructurados con `trace_id`.
   - Metricas por fase del pipeline y por proveedor externo.

## Criterios de aceptacion

- Se preserva compatibilidad funcional de endpoints existentes para el frontend actual.
- El flujo principal queda desacoplado de la capa HTTP en un orquestador dedicado.
- La degradacion por fallas externas mantiene respuesta util y trazable.
- Se cubren pruebas de propiedades para formulas y reglas de clasificacion/validacion clave.
- Exportaciones reflejan de forma consistente recomendaciones, multi-radio y variables ampliadas.

# Esquema de los datos procesados

Diagrama entidad–relación de los datasets de `data/processed/` usados en las
libretas de análisis. Hay una entidad por dataset y, en el caso de
`hidrografia_cd_hermosillo.gpkg`, una por capa (`hl`, `dr`, `ha`, `subc`, `to`).

Las relaciones en **línea continua** (`--`) son llaves reales entre columnas; las
de **línea punteada** (`..`) no son restricciones declaradas: se resuelven en los
jobs o en las libretas (unión por nombre normalizado o unión espacial).

```mermaid
erDiagram
    publicaciones_aguah ||--o{ ubicaciones_aviso : tiene_menciones
    colonias_hermosillo ||--o{ ubicaciones_aviso : contiene
    colonias_hermosillo ||--o{ baches : colonia_normalizada
    colonias_hermosillo ||--o{ llamadas_911_hermosillo : colonia_aproximada
    subc ||--o{ hl : pertenece_a
    dr ||--o{ hl : identifica_drenaje
    colonias_hermosillo }o--o{ hl : interseccion_espacial
    colonias_hermosillo }o--o{ ha : interseccion_espacial

    publicaciones_aguah {
        int64 post_id PK
        string source_slug
        datetime published_at
        int64 year
        int64 month
        int64 iso_week
        int64 day_of_week
        int64 hour_of_day
        string text
        boolean has_text
        string ocr_text
        boolean has_ocr_text
        string ocr_status
        boolean has_image
        int64 reactions_like
        int64 reactions_love
        int64 reactions_haha
        int64 reactions_wow
        int64 reactions_sad
        int64 reactions_angry
        int64 reactions_care
        int64 reactions_total
        float angry_share
        int64 comments_count
        int64 shares_count
        int64 likes_count
        string top_comment_text
        int64 top_comment_likes
        string event_type
        datetime announced_start_at
        boolean has_announced_start_at
        float announced_duration_hours
    }

    ubicaciones_aviso {
        int64 post_id FK
        string location_type
        string raw_text
        string colonia_id FK
        float lat
        float lon
        string source_field
        string match_method
    }

    colonias_hermosillo {
        string colonia_id PK
        string settlement_name
        string settlement_name_normalized
        string settlement_type
        string locality_code
        string postal_code
        float area_km2
        float centroid_lat
        float centroid_lon
        string updated_at
        geometry geometry
    }

    baches {
        int64 id PK
        int64 id_row
        float latitude
        float longitude
        datetime date
        string neighborhoods
        int64 material
        string description
        int64 year
        string date_mx
        string colonia_id FK
    }

    llamadas_911_hermosillo {
        string colonia
        string tipo_incidente
        datetime fecha
        int64 hora
        string grupo_incidente
    }

    subc {
        float ID PK
        string CVE_SUBCUE
        string subcuenca
        geometry geometry
    }

    hl {
        int64 ID PK
        string CVE_SUBC FK
        string CONDICION
        int64 ORDER_1
        int64 ID_DRENA FK
        int64 ENABLED
        string subcuenca
        geometry geometry
    }

    dr {
        int64 ID PK
        string CVE_SUBC
        string CONDICION
        int64 ID_DRENA
        int64 ARBSUM
        string subcuenca
        geometry geometry
    }

    ha {
        int64 IDBD PK
        int64 FC
        string CONDICION
        string subcuenca
        geometry geometry
    }

    toponimos {
        string FC
        string CLASE
        string TERMINO_GE
        string NOMBRE
        string subcuenca
        geometry geometry
    }
```

## Entidades y archivos

| Entidad | Archivo | Una fila representa |
|---|---|---|
| `publicaciones_aguah` | `data/processed/aguah/publicaciones_aguah.csv` | Una publicación de Facebook de Agua de Hermosillo |
| `ubicaciones_aviso` | `data/processed/aguah/ubicaciones_aviso.csv` | Una mención de un lugar (colonia o cruce) dentro de una publicación |
| `colonias_hermosillo` | `data/processed/aguah/colonias_hermosillo.gpkg` (y `.csv`) | Un asentamiento del catálogo DCAH/INEGI con su polígono |
| `baches` | `data/processed/bachometro/baches_hermosillo.csv` | Un reporte ciudadano de bache del Bachómetro |
| `llamadas_911_hermosillo` | `data/processed/llamadas_911/llamadas_911_hermosillo.csv` | Una llamada al 911 por incidente relacionado con agua |
| `subc`, `hl`, `dr`, `ha`, `to` | `data/processed/inegi/hidrografia_hermosillo/hidrografia_cd_hermosillo.gpkg` | Capas INEGI 1:50 000: unidad de captación, cauces, puntos de drenaje, cuerpos de agua y topónimos |

## Notas

- **`ubicaciones_aviso` no tiene llave primaria propia**: cada fila es una mención;
  la misma publicación puede mencionar muchas colonias y cruces (`post_id` se repite).
  `colonia_id` es nulo (~2.4%) cuando `match_method` es `unmatched`, y `lat`/`lon`
  solo existen en `cruce_geocodificado`.
- **`baches` ↔ `colonias_hermosillo`** se resuelve espacialmente: el Bachómetro usa
  sus propios IDs de colonia (`neighborhoods`, no empatables a `colonia_id`). La
  variante `baches_hermosillo_colonia_filled.csv` agrega `colonia_id` (within +
  nearest ≤500 m) con su metodología de match (`spatial_match_method`,
  `distance_to_colonia_m`, `contexto_ubicacion`).
- **`llamadas_911.colonia` es texto libre del operador** (incluye `SIN COLONIA` y
  nombres sin catálogo): no es una llave real; las libretas la unen a
  `colonias_hermosillo` por `settlement_name_normalized` con ~70% de emparejamiento.
- **`colonias_hermosillo` ↔ hidrografía** es una relación puramente espacial
  (intersección de polígonos con segmentos `hl`/`ha` en las libretas); no hay
  columna que la declare. `dr` es un solo punto de drenaje por el área urbana.
- En `hl`, `ORDER_1` es el orden de Strahler del segmento (≥4 colector principal,
  -1 sin clasificar) e `ID_DRENA` apunta al punto de drenaje `dr` que recibe el
  segmento.
- Los perfiles completos por columna (nulos, distintos, rango, descripción) están
  en los diccionarios de esta misma carpeta (`<dataset>.csv` /
  `json/diccionario_<dataset>.json`).

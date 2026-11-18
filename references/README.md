# Referencias

Un diccionario de datos por cada dataset de `data/processed/`, en dos formatos:

- CSV en esta carpeta (`references/<dataset>.csv`), que GitHub renderiza como tabla.
- JSON equivalente en [`json/`](json/) (`json/diccionario_<dataset>.json`).

Cada uno dice qué representa una fila del dataset, cuántas filas tiene y, por columna,
su tipo, porcentaje de nulos, valores distintos, rango y una descripción.

| Diccionario | Archivo procesado | Una fila es |
|---|---|---|
| [`llamadas_911_hermosillo`](llamadas_911_hermosillo.csv) | `llamadas_911/llamadas_911_hermosillo.csv` | una llamada al 911 de los 28 tipos ligados al agua y al terreno |
| [`precipitacion_hermosillo`](precipitacion_hermosillo.csv) | `precipitacion/precipitacion_hermosillo.csv` | un día de lluvia estimada por Open-Meteo |
| [`baches`](baches.csv) | `bachometro/baches_hermosillo.csv` | un bache atendido (fecha de atención) |
| [`baches_con_colonia`](baches_con_colonia.csv) | `bachometro/baches_hermosillo_filled.csv` | un bache atendido con su asentamiento del DCAH |
| [`publicaciones_aguah`](publicaciones_aguah.csv) | `aguah/publicaciones_aguah.csv` | una publicación de Agua de Hermosillo en Facebook |
| [`ubicaciones_aviso`](ubicaciones_aviso.csv) | `aguah/ubicaciones_aviso.csv` | un lugar mencionado en una publicación |
| [`colonias_hermosillo`](colonias_hermosillo.csv) | `aguah/colonias_hermosillo.csv` y `.gpkg` | un asentamiento del municipio (DCAH 2025) |
| [`colonias_contexto_hidrografico`](colonias_contexto_hidrografico.csv) | `inegi/hidrografia_hermosillo/colonias_contexto_hidrografico.csv` | una colonia de la ciudad con sus cauces cercanos y su contexto |
| [`subc_la_manga`](subc_la_manga.csv), [`subc_la_poza`](subc_la_poza.csv), [`subc_r_san_miguel`](subc_r_san_miguel.csv), [`subc_r_son_hillo`](subc_r_son_hillo.csv) | `inegi/subc_*/subc_*.gpkg` | una geometría de una de las 5 capas de la subcuenca |
| [`subc_hermosillo`](subc_hermosillo.csv) | `inegi/hidrografia_hermosillo/subc_hermosillo.gpkg` | lo mismo, con las 4 subcuencas unidas |
| [`hidrografia_cd_hermosillo`](hidrografia_cd_hermosillo.csv) | `inegi/hidrografia_hermosillo/hidrografia_cd_hermosillo.gpkg` | lo mismo, recortado a la ciudad |

Las rutas son relativas a `data/processed/`.

Los genera `make dictionary`: el perfil (tipo, nulos, distintos y rango) lo calcula
pandas sobre los archivos de `data/processed/` y las descripciones viven a mano en
`project_name/metadata/dictionary.py`, que falla si una columna no está descrita o si
sobra una descripción de una columna que ya no existe. En columnas de texto libre el
rango no se publica: su mínimo y su máximo serían valores reales sin agregar.

`data/raw/` (la descarga original, con su `FUENTE.txt`, ver
`project_name/metadata/source.py`) documenta de dónde sale cada dataset; este README
documenta qué forma tiene una vez procesado.

El esquema entidad-relación entre datasets (llaves, uniones por nombre y relaciones
espaciales) está en [`esquema_datos.md`](esquema_datos.md), con un diagrama en
mermaid.

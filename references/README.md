# Referencias

Un diccionario de datos por cada dataset de `data/processed/`, en dos formatos:

- CSV en esta carpeta (`references/<dataset>.csv`), que GitHub renderiza como tabla.
- JSON equivalente en [`json/`](json/) (`json/diccionario_<dataset>.json`).

Cada uno dice qué representa una fila del dataset, cuántas filas tiene y, por columna,
su tipo, porcentaje de nulos, valores distintos, rango y una descripción.

Los genera `make dictionary`: el perfil (tipo, nulos, distintos y rango) lo calcula
pandas sobre los archivos de `data/processed/` y las descripciones viven a mano en
`project_name/metadata/dictionary.py`, que falla si una columna no está descrita o si
sobra una descripción de una columna que ya no existe. En columnas de texto libre el
rango no se publica: su mínimo y su máximo serían valores reales sin agregar.

`data/raw/` (la descarga original, con su `FUENTE.txt`, ver
`project_name/metadata/source.py`) documenta de dónde sale cada dataset; este README
documenta qué forma tiene una vez procesado.

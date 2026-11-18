# Guion de la presentación: lluvia y emergencias urbanas en Hermosillo

Borrador para una exposición de menos de 5 minutos con 4 diapositivas, más 2 de anexo para
preguntas. Presentación: https://claude.ai/artifact/A6hbGbU8HErWAgR1agr2EN

- Duración objetivo: 4 minutos hablando, 1 minuto de margen.
- Ritmo de referencia: unas 140 palabras por minuto, pausado.
- Las cifras salen del reporte ejecutivo (`docs/reporte/reporte.pdf`) y de los notebooks 08
  y 09; el detalle de cada una está en el reporte técnico.

## Plan de tiempos

| Diapositiva | Tema | Tiempo | Acumulado |
|---|---|---:|---:|
| 1 | Portada: cuando llueve, las llamadas se multiplican | 0:40 | 0:40 |
| 2 | Cuánto sube la carga | 1:00 | 1:40 |
| 3 | Qué, a qué hora y dónde | 1:15 | 2:55 |
| 4 | Contraste y qué puede esperar el 911 | 1:05 | 4:00 |
| 5 y 6 | Anexo: cinco V y arquitectura | solo si preguntan | |

## 1. Portada (0:40)

Qué señalar: el título y el "10×".

Guion:

> Buenas tardes. Este proyecto empezó como un inventario de datos de servicios urbanos de
> Hermosillo: reportes de baches, avisos de Agua de Hermosillo y llamadas al 911. Al
> cruzarlos con la lluvia diaria apareció una señal mucho más fuerte que las demás: cuando
> llueve fuerte, las llamadas al 911 por inundaciones, árboles caídos y hundimientos se
> multiplican. Un día con más de 20 milímetros recibe unas diez veces las llamadas de un día
> seco de la temporada. Y no pega igual en toda la ciudad: pesa mucho junto a qué arroyos
> está cada colonia.

Transición:

> Veamos cuánto sube esa carga, y de qué depende.

## 2. Cuánto sube la carga (1:00)

Qué señalar: las barras de izquierda a derecha, y después los dos datos de la derecha.

Guion:

> En Hermosillo llueve fuerte, 10 milímetros o más, unas seis veces al año, y dos de cada
> tres de esos días caen entre julio y septiembre. La gráfica muestra cuántas llamadas recibe
> el 911 en un día de temporada según cuánto llovió. Un día seco recibe 1.7. Con 10 a 20
> milímetros, 9. Con más de 20, entre 17 y 19, y uno de cada diez de esos días pasa de 40.
>
> Y la presión no termina con la tormenta: el día siguiente recibe tantas llamadas como el
> de la lluvia, unas cinco veces un día seco.

Si hay tiempo, una frase de cautela:

> Hubo pocos días de lluvia muy fuerte, así que estas cifras son un orden de magnitud, no un
> pronóstico exacto.

Transición:

> Saber cuánto llega sirve si sabemos qué llega.

## 3. Qué, a qué hora y dónde (1:15)

Qué señalar: las tres tarjetas en orden, de izquierda a derecha.

Guion:

> Primero, qué se reporta. Lo que más crece tras la lluvia son los árboles caídos y las
> inundaciones, cada uno con más de una llamada extra al día; les siguen hundimientos,
> alcantarillas sin tapa y derrumbes. Es trabajo de cuadrillas más que de ambulancias.
>
> Segundo, a qué hora. En un día de lluvia, el 12 por ciento de las llamadas llega de
> madrugada, cuatro veces lo de un día seco, y el pico del día pasa de las 6 a las 9 de la
> noche.
>
> Tercero, dónde. Agrupamos las colonias en cuatro contextos según los tres arroyos más
> cercanos: qué tan grandes son y qué tan cerca pasan. En las colonias junto a los
> colectores principales, sobre todo en el norte, las llamadas suben unas tres veces y media
> al llover frente a días secos del mismo mes, contra 1.4 en las alejadas de la red y casi
> nada junto a arroyos pequeños. Además, sesenta colonias reciben llamadas tras la lluvia en
> tres años o más.

Transición:

> Hasta aquí todo sale del 911. Falta saber si la lluvia mueve también los otros servicios
> del agua con los que empezó el proyecto.

## 4. Contraste y qué puede esperar el 911 (1:05)

Qué señalar: primero las barras de la izquierda; después la lista de la derecha, punto por
punto.

Guion:

> Frente a días secos de la misma temporada, las llamadas por inundación suben 21.7 veces y
> las de árboles y hundimientos casi cuatro. Las emergencias de agua potable no cambian. Y
> los baches no se pueden medir así: el Bachómetro guarda la fecha en que se atiende el
> bache, no cuándo aparece. Por eso el tablero que sigue se centra en el 911.
>
> Para el servicio, esto se traduce en cuatro expectativas. Uno: usar el pronóstico como
> aviso; con 20 milímetros o más, prever unas diez veces las llamadas de un día seco. Dos:
> sostener la carga también al día siguiente. Tres: reforzar la madrugada, con cuadrillas de
> poda, bombeo y tapas listas. Cuatro: revisar antes de julio las colonias junto a los
> cauces principales y las 60 que reinciden.

Cierre:

> Una advertencia para terminar: la lluvia que usamos es una estimación que promedia zonas de
> varios kilómetros, así que las tormentas locales quedan cortas, y estas expectativas
> probablemente también. Gracias.

## Si el tiempo se acaba

En orden, lo que se puede omitir sin perder el hilo:

1. La frase de cautela de la diapositiva 2.
2. El detalle de las horas en la diapositiva 3: decir solo "y llegan de madrugada".
3. La explicación de cómo se ubicaron las llamadas en la diapositiva 3.

No omitir: el 10× de la portada, las barras de la diapositiva 2, el contraste con baches y la
lista de expectativas.

## Preguntas probables

| Pregunta | Respuesta corta | Apoyo |
|---|---|---|
| ¿Por qué el 911 y no los baches, si el proyecto empezó con baches? | Porque el Bachómetro registra la fecha en que se atiende el bache (días hábiles, descripciones "Bacheo en…"), no cuándo aparece: no sirve para medir el efecto de la lluvia. Las emergencias de agua potable sí se pueden medir y no cambian (1.0×). | Diapositiva 4; reporte técnico |
| ¿Es una relación causal? | Es diagnóstica, no una prueba causal: se compara contra días secos de la misma temporada y del mismo mes, lo que quita calor, vacaciones y tendencia. Hay pocos días de lluvia muy fuerte. | Reporte técnico, secciones 4 y 8 |
| ¿De dónde sale la lluvia? | De Open-Meteo, una estimación diaria para un punto de la ciudad. No es una estación; una estación de CONAGUA mejoraría la medición de tormentas locales. | Anexo, diapositiva 5 |
| ¿Cuántos datos son? | El archivo del 911 trae 2,297,081 llamadas; usamos 4,176 de 28 tipos ligados al agua y al terreno, de 2018 a 2025. En total, unos 404 MB crudos en ocho fuentes. | Anexo, diapositiva 5 |
| ¿Por qué una de cada cinco llamadas no tiene colonia? | El 911 captura la colonia como texto libre, con abreviaturas y variantes. Se asigna por nombre contra el catálogo del INEGI y, para las variantes, con una tabla de equivalencias revisada a mano por el equipo (data/external/equivalencias_colonias_911.csv): así se ubica 80.4%. | Reporte técnico |
| ¿Las 60 colonias son las más pobladas? | No tenemos población por colonia; sí sabemos que son grandes (área mediana siete veces la del conjunto), así que parte del efecto es tamaño. | Reporte ejecutivo, pregunta 3 |
| ¿Los cauces explican dónde llaman? | En parte. Agrupadas por su contexto hidrográfico, las colonias junto a los colectores principales responden más a la lluvia (3.5 veces dentro del mismo mes, intervalo 1.7 a 7.2) que las alejadas de la red (1.4; 1.0 a 2.2). Colonia por colonia, la distancia al cauce sola dice poco. | Notebook 10 |
| ¿Por qué no cuentan los ahogamientos? | Son pocos (84 en ocho años) y no dependen de la lluvia en la ciudad. | Reporte técnico, sección 2 |
| ¿Cómo se puede reproducir? | `make download` y `make data` rehacen los datos; los notebooks 08 y 09 rehacen las cifras y las gráficas. | Anexo, diapositiva 6 |
| ¿Qué sigue? | El tablero para el 911: llamadas esperadas según el pronóstico de lluvia y el mapa de colonias por temporada. | Diapositiva 6, etapa 5 |

## Antes de presentar

- Llenar los nombres del equipo en la portada (hoy dice "[Integrantes del equipo]").
- Compartir la presentación desde el menú Share; hoy solo la puede abrir su dueño.
- Ensayar con cronómetro una vez completa; si pasa de 4:30, aplicar los recortes de arriba.
- Repartir las diapositivas si presentan varios: por ejemplo, una persona para 1 y 2 y otra
  para 3 y 4, con el cambio en la transición "Saber cuánto llega sirve si sabemos qué llega".
- Tener a la mano el PDF del reporte ejecutivo por si se pide una cifra que no está en las
  diapositivas.
- Descargar una copia en PDF de la presentación por si falla la conexión.

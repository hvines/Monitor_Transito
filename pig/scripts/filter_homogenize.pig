-- pig/scripts/filter_homogenize.pig

-- 1. Cargar el CSV (suponemos que usa coma como separador y hay header)
events_raw = LOAD '/data/raw/events.csv'
    USING PigStorage(',')
    AS (uuid:chararray, type:chararray, location:chararray, timestamp:chararray);

-- 2. Saltar la fila del encabezado
events_no_header = FILTER events_raw BY uuid != 'uuid';

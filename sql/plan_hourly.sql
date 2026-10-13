-- Por estación × día local × hora: fracción del tiempo vacía, llena y sin
-- eléctricas, solo con la estación instalada y prestando. Tipo de día: lab
-- (lunes-viernes no festivo), sab, dom (domingos y festivos).
-- Para analysis/plan_calibration.py.
COPY (
  WITH m AS (
    SELECT station_id, (ts AT TIME ZONE 'Europe/Madrid') AS lt,
           bikes_available, docks_available, coalesce(electric_available, 0) AS el
    FROM dbizi_measurement
    WHERE is_installed AND coalesce(is_renting, true)
  )
  SELECT m.station_id, m.lt::date AS day,
         CASE WHEN h.date IS NOT NULL OR extract(isodow FROM m.lt) = 7 THEN 'dom'
              WHEN extract(isodow FROM m.lt) = 6 THEN 'sab' ELSE 'lab' END AS daytype,
         extract(hour FROM m.lt)::int AS hour,
         avg((bikes_available = 0)::int) AS p_empty,
         avg((docks_available = 0)::int) AS p_full,
         avg((el = 0)::int) AS p_noelec,
         count(*) AS n
  FROM m LEFT JOIN holiday h ON h.date = m.lt::date
  GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 4
) TO STDOUT CSV HEADER;

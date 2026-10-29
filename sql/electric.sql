-- Eléctricas frente a mecánicas, por estación × día local × hora, para analysis/electric.py.
-- Salidas/llegadas por tipo con la regla del timelapse (|delta total|<6, abierta,
-- <=5 min entre capturas) y sin las capturas en que cambian las averiadas (no
-- sabemos de qué tipo son). Además disponibilidad media por tipo, fracción del
-- tiempo sin eléctricas (con mecánicas) y viceversa, y salidas por tipo contadas
-- solo mientras había de los dos (para medir preferencia sin censura).
COPY (
  WITH m AS (
    SELECT station_id, (ts AT TIME ZONE 'Europe/Madrid') AS lt,
           bikes_available AS b, coalesce(electric_available,0) AS e, coalesce(mechanical_available,0) AS mc,
           bikes_available - lag(bikes_available) OVER w AS db,
           coalesce(electric_available,0) - lag(coalesce(electric_available,0)) OVER w AS de,
           coalesce(mechanical_available,0) - lag(coalesce(mechanical_available,0)) OVER w AS dm,
           coalesce(vehicles_disabled,0) - lag(coalesce(vehicles_disabled,0)) OVER w AS dd,
           (is_installed AND lag(is_installed) OVER w AND coalesce(is_renting,true)) AS ok,
           ts - lag(ts) OVER w AS gap,
           lag(coalesce(electric_available,0)) OVER w AS e0, lag(coalesce(mechanical_available,0)) OVER w AS m0
    FROM dbizi_measurement
    WINDOW w AS (PARTITION BY station_id ORDER BY ts)
  ), v AS (
    SELECT *, (db IS NOT NULL AND ok AND gap <= interval '5 min' AND abs(db) < 6 AND dd = 0) AS valid FROM m
  )
  SELECT station_id, lt::date AS day,
         CASE WHEN h.date IS NOT NULL OR extract(isodow FROM lt) = 7 THEN 'dom'
              WHEN extract(isodow FROM lt) = 6 THEN 'sab' ELSE 'lab' END AS daytype,
         extract(hour FROM lt)::int AS hour,
         -- por tipo, acotado al total: una reclasificación (e->m sin cambiar el total) no es un viaje
         sum(CASE WHEN valid THEN least(greatest(0,-de), greatest(0,-db)) ELSE 0 END) AS dep_e,
         sum(CASE WHEN valid THEN least(greatest(0, de), greatest(0, db)) ELSE 0 END) AS arr_e,
         sum(CASE WHEN valid THEN greatest(0,-db) - least(greatest(0,-de), greatest(0,-db)) ELSE 0 END) AS dep_m,
         sum(CASE WHEN valid THEN greatest(0, db) - least(greatest(0, de), greatest(0, db)) ELSE 0 END) AS arr_m,
         sum(CASE WHEN valid AND e0 > 0 AND m0 > 0 THEN least(greatest(0,-de), greatest(0,-db)) ELSE 0 END) AS dep_e_both,
         sum(CASE WHEN valid AND e0 > 0 AND m0 > 0 THEN greatest(0,-db) - least(greatest(0,-de), greatest(0,-db)) ELSE 0 END) AS dep_m_both,
         avg(CASE WHEN e > 0 AND mc > 0 THEN e END) AS avg_e_both,
         avg(CASE WHEN e > 0 AND mc > 0 THEN mc END) AS avg_m_both,
         avg(e) AS avg_e, avg(mc) AS avg_m,
         avg((e = 0 AND mc > 0)::int) AS p_noelec, avg((mc = 0 AND e > 0)::int) AS p_nomech,
         avg((b = 0)::int) AS p_empty, count(*) AS n
  FROM v LEFT JOIN holiday h ON h.date = v.lt::date
  WHERE ok
  GROUP BY 1, 2, 3, 4 HAVING count(*) >= 10 ORDER BY 1, 2, 4
) TO STDOUT CSV HEADER;

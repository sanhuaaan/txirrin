-- Eventos unitarios para analysis/night_trips.py: cada cambio de bikes_available
-- entre dos snapshots consecutivos (<=5 min), descontando averías (vehicles_disabled)
-- y descartando saltos >=6 (camión) y estaciones cerradas. dep/arr en unidades.
COPY (
  WITH d AS (
    SELECT station_id, ts,
           bikes_available - lag(bikes_available) OVER w AS df,
           coalesce(vehicles_disabled,0) - lag(coalesce(vehicles_disabled,0)) OVER w AS db,
           (is_installed AND lag(is_installed) OVER w) AS inst,
           ts - lag(ts) OVER w AS gap
    FROM dbizi_measurement
    WINDOW w AS (PARTITION BY station_id ORDER BY ts)
  )
  SELECT station_id, ts,
         greatest(0, -df - greatest(0, db)) AS dep,
         greatest(0,  df - greatest(0,-db)) AS arr
  FROM d
  WHERE df IS NOT NULL AND inst AND gap <= interval '5 min' AND abs(df) < 6
    AND (greatest(0, -df - greatest(0, db)) > 0 OR greatest(0, df - greatest(0,-db)) > 0)
  ORDER BY ts
) TO STDOUT CSV HEADER;

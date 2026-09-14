-- Viajes estimados por día (hora local), con la misma regla que el timelapse:
-- delta de 2 min por estación; |delta|>=6 es camión, no cuenta; una bici que
-- pasa a averiada no es una salida. viajes ~ (salidas+llegadas)/2.
COPY (
  WITH d AS (
    SELECT ts, station_id, is_installed,
           bikes_available - lag(bikes_available) OVER w AS df,
           coalesce(vehicles_disabled,0) - lag(coalesce(vehicles_disabled,0)) OVER w AS db,
           lag(is_installed) OVER w AS prev_inst
    FROM dbizi_measurement
    WINDOW w AS (PARTITION BY station_id ORDER BY ts)
  )
  SELECT (ts AT TIME ZONE 'Europe/Madrid')::date AS day,
         sum(greatest(0, -df - greatest(0, db))) AS dep,
         sum(greatest(0,  df - greatest(0,-db))) AS arr,
         count(DISTINCT ts) AS n_snaps
  FROM d
  WHERE df IS NOT NULL AND abs(df) < 6 AND is_installed AND prev_inst
  GROUP BY 1 ORDER BY 1
) TO STDOUT CSV HEADER;

-- Series a 15 min por estación para analysis/forecast_eval.py:
-- media de bicis en el cuarto de hora + capacidad. UTC; el script localiza.
COPY (
  SELECT m.station_id,
         to_timestamp(floor(extract(epoch FROM m.ts) / 900) * 900) AT TIME ZONE 'UTC' AS ts,
         avg(m.bikes_available) AS bikes,
         max(s.capacity) AS capacity
  FROM dbizi_measurement m JOIN dbizi_station s USING (station_id)
  WHERE m.is_installed
  GROUP BY 1, 2 ORDER BY 1, 2
) TO STDOUT CSV HEADER;

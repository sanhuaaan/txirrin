-- Agregado horario por estación y tipo de día (hora local) para analysis/profiles.py
-- docker exec -i dbizi-postgres-1 psql -U dbizi -d dbizi < profiles.sql > profiles.csv
COPY (
  SELECT m.station_id, s.name, ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon,
         CASE WHEN extract(isodow FROM m.ts AT TIME ZONE 'Europe/Madrid') >= 6 THEN 'weekend' ELSE 'weekday' END AS daytype,
         extract(hour FROM m.ts AT TIME ZONE 'Europe/Madrid')::int AS hour,
         avg(m.bikes_available::float / nullif(m.bikes_available + m.docks_available, 0)) AS occ,
         avg(m.bikes_available) AS bikes,
         avg(m.electric_available) AS elec,
         avg(m.mechanical_available) AS mech,
         avg((m.bikes_available = 0)::int) AS p_empty,
         avg((m.docks_available = 0)::int) AS p_full,
         count(*) AS n
  FROM dbizi_measurement m JOIN dbizi_station s USING (station_id)
  WHERE m.is_installed
  GROUP BY 1,2,3,4,5,6 ORDER BY 1,5,6
) TO STDOUT CSV HEADER;

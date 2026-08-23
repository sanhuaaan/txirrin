-- Esquema mínimo MVP. El crudo completo vive en ~/raw/YYYYMMDD/*.json.gz (y su copia
-- en GCS); scripts/ingest_raw.py lo reingesta, así que un fallo de BD no pierde el tick.
-- Re-ejecutable tal cual: los ALTER/UPDATE del final migran una BD ya poblada.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS dbizi_station (
    station_id text PRIMARY KEY,
    name       text NOT NULL,
    geom       geometry(Point, 4326) NOT NULL,
    capacity   integer,
    address    text,
    post_code  text,
    source     text NOT NULL DEFAULT 'gbfs',
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Sin FK a dbizi_station: una estación nueva en station_status no debe tumbar la ingesta.
CREATE TABLE IF NOT EXISTS dbizi_measurement (
    station_id           text NOT NULL,
    ts                   timestamptz NOT NULL, -- last_updated del feed (instante del snapshot)
    fetched_at           timestamptz,          -- cuándo lo capturamos: si el feed se congela, ts deja
                                               -- de avanzar y solo esto distingue feed parado de collector caído
    bikes_available      integer,
    docks_available      integer,
    -- OJO: mechanical + electric puede NO cuadrar con bikes_available (visto en ~1 de 70
    -- estaciones; PBSC reporta vehicle_types_available desacompasado). No apilar sobre el total.
    mechanical_available integer,
    electric_available   integer,
    vehicles_disabled    integer, -- bicis averiadas: señal de salud de estación
    docks_disabled       integer,
    bikes_overflow       integer,
    is_installed         boolean,
    is_renting           boolean,
    is_returning         boolean,
    last_reported        timestamptz,
    PRIMARY KEY (station_id, ts)
);

CREATE INDEX IF NOT EXISTS dbizi_measurement_ts_idx ON dbizi_measurement (ts);

CREATE TABLE IF NOT EXISTS weather_station (
    station_id text PRIMARY KEY,
    name       text NOT NULL,
    geom       geometry(Point, 4326) NOT NULL,
    altitude   integer,
    source     text NOT NULL DEFAULT 'euskalmet'
);

CREATE TABLE IF NOT EXISTS weather_measurement (
    station_id       text NOT NULL,
    ts               timestamptz NOT NULL, -- UTC (verificado: el día del cambio horario trae 144 lecturas)
    interval_minutes smallint,             -- paso de la serie: C017=10, OPENMETEO=60
    temperature      real,                 -- °C
    -- mm ACUMULADOS EN interval_minutes, no una tasa: C017 da mm/10min y Open-Meteo mm/hora.
    -- Sumar por día funciona en cada serie; comparar umbrales entre ambas NO.
    -- Para mm/h homogéneos: precipitation * 60.0 / interval_minutes
    precipitation    real,
    humidity         real,                 -- %
    wind_speed       real,                 -- m/s (media del intervalo)
    wind_max         real,                 -- m/s (racha)
    wind_dir         real,                 -- grados
    irradiance       real,
    PRIMARY KEY (station_id, ts)
);

CREATE TABLE IF NOT EXISTS holiday (
    date date PRIMARY KEY,
    name text NOT NULL
);

-- Eventos con hora y sitio: deporte (Real Sociedad, Gipuzkoa Basket) y pruebas
-- populares. Kulturklik sigue en ficheros (~/events/): no trae hora ni recinto
-- geolocalizado. Esta tabla es, de paso, el "venue -> coords" de la Fase 0.
CREATE TABLE IF NOT EXISTS event (
    id           text PRIMARY KEY,          -- fuente:clave estable
    source       text NOT NULL,             -- openfootball | thesportsdb | manual
    kind         text NOT NULL,             -- futbol | baloncesto | carrera | regata | ciclismo
    name         text NOT NULL,
    starts_at    timestamptz NOT NULL,
    ends_at      timestamptz,
    venue        text,
    lat          double precision,
    lon          double precision,
    confirmed    boolean NOT NULL DEFAULT true,  -- false: fecha/hora provisional
    harvested_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS event_starts_at_idx ON event (starts_at);

-- Migraciones idempotentes (no-op en BD nueva; migran la existente en la VM).
ALTER TABLE dbizi_measurement   ADD COLUMN IF NOT EXISTS fetched_at       timestamptz;
ALTER TABLE weather_measurement ADD COLUMN IF NOT EXISTS interval_minutes smallint;
UPDATE weather_measurement SET interval_minutes = 10 WHERE station_id = 'C017'      AND interval_minutes IS NULL;
UPDATE weather_measurement SET interval_minutes = 60 WHERE station_id = 'OPENMETEO' AND interval_minutes IS NULL;

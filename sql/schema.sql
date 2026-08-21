-- Esquema mínimo MVP. El crudo completo vive en el historial de dbizi-raw; no se duplica aquí.
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

-- ponytail: sin FK a dbizi_station — una estación nueva en station_status no debe tumbar la ingesta
CREATE TABLE IF NOT EXISTS dbizi_measurement (
    station_id           text NOT NULL,
    ts                   timestamptz NOT NULL, -- last_updated del feed (instante del snapshot)
    bikes_available      integer,
    docks_available      integer,
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
    station_id    text NOT NULL,
    ts            timestamptz NOT NULL, -- UTC (verificado: el día del cambio horario trae 144 lecturas)
    temperature   real,                 -- °C
    precipitation real,                 -- mm en 10 min
    humidity      real,                 -- %
    wind_speed    real,                 -- m/s (media 10 min)
    wind_max      real,                 -- m/s (racha)
    wind_dir      real,                 -- grados
    irradiance    real,
    PRIMARY KEY (station_id, ts)
);

CREATE TABLE IF NOT EXISTS holiday (
    date date PRIMARY KEY,
    name text NOT NULL
);

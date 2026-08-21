-- Festivos Donostia 2026 (nacionales + País Vasco + Gipuzkoa + locales Donostia).
-- Tabla a mano por diseño: ~14 filas/año; añadir el año siguiente cada diciembre.
-- Verificar contra el calendario laboral oficial (BOG) al añadir cada año.
INSERT INTO holiday (date, name) VALUES
    ('2026-01-01', 'Año Nuevo'),
    ('2026-01-06', 'Epifanía'),
    ('2026-01-20', 'San Sebastián (local Donostia)'),
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-04-06', 'Lunes de Pascua'),
    ('2026-05-01', 'Fiesta del Trabajo'),
    ('2026-07-25', 'Santiago Apóstol'),
    ('2026-07-31', 'San Ignacio (Gipuzkoa)'),
    ('2026-08-15', 'Asunción'),
    ('2026-10-12', 'Fiesta Nacional'),
    ('2026-11-01', 'Todos los Santos'),
    ('2026-12-06', 'Día de la Constitución'),
    ('2026-12-08', 'Inmaculada Concepción'),
    ('2026-12-25', 'Navidad')
ON CONFLICT (date) DO NOTHING;

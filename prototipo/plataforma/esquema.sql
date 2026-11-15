-- SIVIA · esquema de la plataforma en PostgreSQL (Neon u otro).
-- Se puede correr varias veces: solo crea lo que falta.

CREATE TABLE IF NOT EXISTS instituciones (
    id                    text PRIMARY KEY,           -- id del DENUE (INEGI, catálogo #09)
    nombre                text NOT NULL,
    tipo                  text,
    codigo_scian          text,
    zona                  text,
    direccion             text,
    colonia               text,
    lat                   double precision NOT NULL,
    lng                   double precision NOT NULL,
    accidentes_200m       integer DEFAULT 0,           -- ATUS INEGI 2022-2024 (catálogo #08)
    atropellamientos_200m integer DEFAULT 0,
    heridos_200m          integer DEFAULT 0,
    muertos_200m          integer DEFAULT 0
);
CREATE INDEX IF NOT EXISTS instituciones_zona ON instituciones (zona);

CREATE TABLE IF NOT EXISTS imagenes (
    archivo        text PRIMARY KEY,                   -- mly_<id>.jpg
    institucion_id text REFERENCES instituciones (id),
    fuente         text NOT NULL DEFAULT 'mapillary',  -- mapillary | camara_propia
    fecha_captura  text,
    lat            double precision,
    lng            double precision,
    autor          text,                               -- crédito CC BY-SA 4.0
    bucket_key     text                                -- llave en el bucket, cuando ya se subió
);
CREATE INDEX IF NOT EXISTS imagenes_institucion ON imagenes (institucion_id);

CREATE TABLE IF NOT EXISTS detecciones (
    id        bigserial PRIMARY KEY,
    archivo   text NOT NULL REFERENCES imagenes (archivo),
    modelo    text NOT NULL,                           -- p. ej. yolo11s_v8
    clase     text NOT NULL,
    confianza real NOT NULL,
    umbral    real,
    x integer, y integer, w integer, h integer,        -- píxeles de la imagen original
    fuente    text NOT NULL DEFAULT 'modelo',          -- modelo | mapillary
    creada_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS detecciones_archivo ON detecciones (archivo);

CREATE TABLE IF NOT EXISTS candidatos (
    id             text PRIMARY KEY,                   -- ia_<id de imagen>, igual que en el tablero
    archivo        text REFERENCES imagenes (archivo),
    institucion_id text REFERENCES instituciones (id),
    clase          text NOT NULL,
    confianza      real NOT NULL,
    estado         text NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente', 'confirmado', 'descartado')),
    revisado_en    timestamptz,
    revisado_por   text
);

CREATE TABLE IF NOT EXISTS ordenes (
    id             text PRIMARY KEY,                   -- <institucion_id>:<clave>, estable entre cargas
    institucion_id text REFERENCES instituciones (id),
    clave          text NOT NULL,
    hallazgo       text NOT NULL,
    dependencia    text NOT NULL,
    prioridad_base real NOT NULL,
    factor_clima   real NOT NULL DEFAULT 1,
    prioridad      real NOT NULL,
    detecciones    integer,
    imagen         text,
    explicacion    text,
    estado         text NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente', 'asignada', 'en_atencion', 'resuelta', 'descartada')),
    creada_en      timestamptz NOT NULL DEFAULT now(),
    actualizada_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ordenes_dependencia ON ordenes (dependencia, prioridad DESC);

CREATE TABLE IF NOT EXISTS eventos (               -- bitácora: quién cambió qué y cuándo
    id       bigserial PRIMARY KEY,
    tabla    text NOT NULL,                        -- candidatos | ordenes
    registro text NOT NULL,
    estado   text NOT NULL,
    usuario  text,
    nota     text,
    fecha    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pronosticos (           -- copias del pronóstico SMN usado para priorizar
    id       bigserial PRIMARY KEY,
    fuente   text NOT NULL,
    datos    jsonb NOT NULL,
    fecha    timestamptz NOT NULL DEFAULT now()
);

-- Línea base por zona (indicador 1 del reporte: cobertura de la inspección)
CREATE OR REPLACE VIEW cobertura_zona AS
SELECT i.zona,
       count(DISTINCT i.id)                             AS instituciones,
       count(DISTINCT im.institucion_id)                AS con_imagenes,
       round(100.0 * count(DISTINCT im.institucion_id) / count(DISTINCT i.id), 1) AS pct_cobertura,
       (SELECT count(*) FROM ordenes o JOIN instituciones i2 ON i2.id = o.institucion_id
         WHERE i2.zona = i.zona)                        AS ordenes
FROM instituciones i
LEFT JOIN imagenes im ON im.institucion_id = i.id
GROUP BY i.zona;

CREATE TABLE public.ships (
    id integer NOT NULL,
    "timestamp" timestamp without time zone,
    mmsi bigint,
    latitude numeric(9,6),
    longitude numeric(9,6),
    speed numeric(5,2),
    image_path text,
    name text,
    destination text,
    eta text,
    navigation_status text,
    heading double precision
);

-- Set up the auto-incrementing primary key
CREATE SEQUENCE public.ships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE ONLY public.ships ALTER COLUMN id SET DEFAULT nextval('public.ships_id_seq'::regclass);

-- Add primary key constraint
ALTER TABLE ONLY public.ships
    ADD CONSTRAINT ships_pkey PRIMARY KEY (id);
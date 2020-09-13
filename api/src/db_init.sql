--
-- PostgreSQL database dump
--

-- Dumped from database version 12.4 (Debian 12.4-1.pgdg100+1)
-- Dumped by pg_dump version 12.4 (Ubuntu 12.4-0ubuntu0.20.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE SCHEMA shortlinks;
ALTER SCHEMA shortlinks OWNER TO postgres;

CREATE TYPE shortlinks.shortlink_status AS ENUM (
    'active',
    'inactive',
    'free'
);
ALTER TYPE shortlinks.shortlink_status OWNER TO postgres;

SET default_tablespace = '';
SET default_table_access_method = heap;

CREATE TABLE shortlinks.link (
    id integer NOT NULL,
    short character varying(6),
    origin text,
    date_access timestamp without time zone NOT NULL,
    status shortlinks.shortlink_status NOT NULL
);
ALTER TABLE shortlinks.link OWNER TO postgres;

CREATE SEQUENCE shortlinks.link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER TABLE shortlinks.link_id_seq OWNER TO postgres;
ALTER SEQUENCE shortlinks.link_id_seq OWNED BY shortlinks.link.id;
ALTER TABLE ONLY shortlinks.link ALTER COLUMN id SET DEFAULT nextval('shortlinks.link_id_seq'::regclass);
SELECT pg_catalog.setval('shortlinks.link_id_seq', 1, false);

ALTER TABLE ONLY shortlinks.link
    ADD CONSTRAINT link_pkey PRIMARY KEY (id);

CREATE INDEX date_access_status ON shortlinks.link USING btree (date_access, status);
CREATE UNIQUE INDEX short ON shortlinks.link USING btree (short);
CREATE INDEX short_status ON shortlinks.link USING btree (short, status);
CREATE INDEX status ON shortlinks.link USING btree (status);


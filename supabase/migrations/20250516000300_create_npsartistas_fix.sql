-- Cria a tabela npsartistas
create table if not exists public.npsartistas (
  id                uuid primary key,
  data              date,
  nps_eshows        smallint,
  csat_eshows       smallint,
  operador_1        text,
  operador_2        text,
  csat_operador_1   smallint,
  csat_operador_2   smallint
);

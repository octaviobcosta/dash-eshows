-- +goose up
create table public.custosabertos (
  id_custo         bigint primary key,
  grupo_geral      text   not null,
  nivel_1          text   not null,
  nivel_2          text   not null,
  fornecedor       text   not null,
  valor            bigint not null,      -- em centavos
  pagamento        text   not null,
  data_competencia date   not null,
  data_vencimento  date   not null
);

create index custosabertos_data_competencia_idx
  on public.custosabertos (data_competencia);

-- +goose down
drop table if exists public.custosabertos;

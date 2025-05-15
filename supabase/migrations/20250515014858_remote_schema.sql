create sequence "public"."boletoartistas_idx_seq";

create table "public"."backup" (
    "p_ID" bigint not null,
    "Casa" text,
    "c_ID" bigint,
    "UF" character(2),
    "Cidade" text,
    "Data" date,
    "Data_Pagamento" date,
    "Artista" text,
    "Valor_Bruto" bigint,
    "Valor_Total" bigint,
    "Valor_Liquido" bigint,
    "B2C" bigint,
    "Comissao_Eshows_B2B" bigint,
    "Comissao_Eshows_B2C" bigint,
    "Taxa_Adiantamento" bigint,
    "Curadoria" bigint,
    "SAAS_Percentual" bigint,
    "SAAS_Mensalidade" bigint,
    "Fk_Sem_Curadoria" bigint,
    "Taxa_Emissao_NF" bigint,
    "Primeiro_Dia_Mes" date,
    "Semana_Ano" integer,
    "GRUPO_CLIENTES" text,
    "NOTA" numeric(4,2),
    "Dia" smallint,
    "Mes" smallint,
    "Ano" smallint
);


create table "public"."base2" (
    "Mes Ref" text not null,
    "Mes_ord2" smallint,
    "Ano" smallint,
    "Mes_ord" smallint,
    "Custos" bigint,
    "Imposto" bigint,
    "Ocupação" bigint,
    "Equipe" bigint,
    "Terceiros" bigint,
    "Op. Shows" bigint,
    "D.Cliente" bigint,
    "Softwares" bigint,
    "Mkt" bigint,
    "D.Finan" bigint,
    "C. Comercial" bigint,
    "C. Tecnologia" bigint,
    "C. Geral" bigint,
    "C. Recursos Humanos" bigint,
    "C. Customer Success" bigint,
    "C. Operações" bigint,
    "C. Novos Produtos" bigint,
    "C. Contabilidade" bigint,
    "C. Marketing" bigint,
    "Custo Farm" bigint,
    "Custo Hunt" bigint,
    "Comercial" bigint,
    "Tech" bigint,
    "Geral" bigint,
    "Financas" bigint,
    "Control" bigint,
    "Juridico" bigint,
    "C.Sucess" bigint,
    "Operações" bigint,
    "RH" bigint,
    "Propostas Lancadas Internas" integer,
    "Propostas Lancadas Usuários" integer,
    "NPS Equipe" numeric(4,1),
    "NPS Artistas" numeric(4,1),
    "Projetos Cadastrados" integer,
    "Projetos Incompletos" integer,
    "Projetos Parciais" integer,
    "Projetos Completos" integer,
    "Base Acumulada Total" integer,
    "Base Acumulada Incompleta" integer,
    "Base Acumulada Parcial" integer,
    "Base Acumulada Completa" integer,
    "Tempo Resposta" text,
    "Tempo Resolução" text,
    "Uptime (%)" numeric(5,2),
    "MTBF (horas)" numeric(10,2),
    "MTTR (Min)" numeric(10,2),
    "Taxa de Erros (%)" numeric(5,2),
    "CAC" numeric(14,2)
);


create table "public"."baseeshows" (
    "p_ID" bigint not null,
    "Casa" text,
    "c_ID" bigint,
    "UF" character(2),
    "Cidade" text,
    "Data" date,
    "Data_Pagamento" date,
    "Artista" text,
    "Valor_Bruto" bigint,
    "Valor_Total" bigint,
    "Valor_Liquido" bigint,
    "B2C" bigint,
    "Comissao_Eshows_B2B" bigint,
    "Comissao_Eshows_B2C" bigint,
    "Taxa_Adiantamento" bigint,
    "Curadoria" bigint,
    "SAAS_Percentual" bigint,
    "SAAS_Mensalidade" bigint,
    "Fk_Sem_Curadoria" bigint,
    "Taxa_Emissao_NF" bigint,
    "Primeiro_Dia_Mes" date,
    "Semana_Ano" integer,
    "GRUPO_CLIENTES" text,
    "NOTA" numeric(4,2),
    "Dia" smallint,
    "Mes" smallint,
    "Ano" smallint
);


create table "public"."boletoartistas" (
    "ID_Boleto" bigint not null,
    "ID" bigint,
    "NOME" text,
    "Data_Show" text,
    "DATA_PAGAMENTO" text,
    "Adiantamento" text,
    "N_NF" text,
    "Link_NF" text,
    "Valor_Bruto" bigint,
    "idx" bigint not null default nextval('boletoartistas_idx_seq'::regclass)
);


create table "public"."boletocasas" (
    "ID_Boleto" bigint not null,
    "Casa" text,
    "Data Inicio" text,
    "Data Fim" text,
    "Data Geração" date,
    "Data Vencimento" date,
    "Valor" bigint,
    "Valor_Real" bigint,
    "Status" text,
    "DiaVenc" smallint,
    "MesVenc" smallint,
    "AnoVenc" smallint
);


create table "public"."metas" (
    "index" bigint not null,
    "Ano" smallint,
    "Mes" numeric,
    "Novos_Clientes" bigint,
    "Key_Account" bigint,
    "Outros_Clientes" bigint,
    "Curadoria" bigint,
    "Fintech" bigint,
    "Fat_Total" bigint,
    "InadimplenciaReal" text,
    "Lucratividade" text,
    "NRR" text,
    "Perdas_Operacionais" text,
    "Palcos_Vazios" bigint,
    "Nivel_Servico" text,
    "Churn" text,
    "TurnOver" text,
    "Ef_Atendimento" text,
    "Estabilidade" text,
    "Crescimento_Sustentavel" text,
    "Conformidade_Juridica" text,
    "NPS_Equipe" text,
    "NPS_Contratante" text,
    "NPS_Artistas" text,
    "CSAT_Atendimento" text,
    "Mes Nome" text,
    "LTV/CAC" text,
    "LTV_CAC" text
);


create table "public"."pessoas" (
    "Name" text not null,
    "Subelementos" numeric,
    "Status" text,
    "Empresa" text,
    "RG" text,
    "CPF" text,
    "Foto_doc" text,
    "Data_inicio" date,
    "Job_description" text,
    "Genero" text,
    "Área" text,
    "Senioridade" text,
    "Email_Pessoal" text,
    "Email_Eshows" text,
    "Telefone" text,
    "Data_nascimento" date,
    "Cartao_Alimentacao" text,
    "Valor_Alimentacao" bigint,
    "Equipamento da Empresa" text,
    "Descrição Equipamento" text,
    "Termo de Comodato" text,
    "Regular" text,
    "Recisão" numeric,
    "Data_Saida" date,
    "Tipo_Saida" text,
    "Tipo_vinculo" text,
    "Mes_Inicio" smallint,
    "Ano_Inicio" smallint,
    "Mes_Saida" smallint,
    "Ano_Saida" smallint,
    "Endereço" text,
    "Salário Mensal" text,
    "Pró-Labore" text,
    "Contrato" text,
    "Status Contrato" text
);


CREATE UNIQUE INDEX "Base2_pkey" ON public.base2 USING btree ("Mes Ref");

CREATE INDEX "BaseEshows_Casa_idx" ON public.backup USING btree ("Casa");

CREATE INDEX "BaseEshows_Data_idx" ON public.backup USING btree ("Data");

CREATE UNIQUE INDEX "BaseEshows_pkey" ON public.backup USING btree ("p_ID");

CREATE UNIQUE INDEX "Metas_pkey" ON public.metas USING btree (index);

CREATE INDEX "baseeshows_duplicate_Casa_idx" ON public.baseeshows USING btree ("Casa");

CREATE INDEX "baseeshows_duplicate_Data_idx" ON public.baseeshows USING btree ("Data");

CREATE UNIQUE INDEX baseeshows_duplicate_pkey ON public.baseeshows USING btree ("p_ID");

CREATE UNIQUE INDEX boletoartistas_duplicate_pkey ON public.boletoartistas USING btree (idx);

CREATE UNIQUE INDEX boletocasas_duplicate_pkey ON public.boletocasas USING btree ("ID_Boleto");

CREATE UNIQUE INDEX pessoas_duplicate_pkey ON public.pessoas USING btree ("Name");

alter table "public"."backup" add constraint "BaseEshows_pkey" PRIMARY KEY using index "BaseEshows_pkey";

alter table "public"."base2" add constraint "Base2_pkey" PRIMARY KEY using index "Base2_pkey";

alter table "public"."baseeshows" add constraint "baseeshows_duplicate_pkey" PRIMARY KEY using index "baseeshows_duplicate_pkey";

alter table "public"."boletoartistas" add constraint "boletoartistas_duplicate_pkey" PRIMARY KEY using index "boletoartistas_duplicate_pkey";

alter table "public"."boletocasas" add constraint "boletocasas_duplicate_pkey" PRIMARY KEY using index "boletocasas_duplicate_pkey";

alter table "public"."metas" add constraint "Metas_pkey" PRIMARY KEY using index "Metas_pkey";

alter table "public"."pessoas" add constraint "pessoas_duplicate_pkey" PRIMARY KEY using index "pessoas_duplicate_pkey";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.col_exists(col text)
 RETURNS boolean
 LANGUAGE sql
AS $function$
      select exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name   = 'Metas'
          and column_name  = col
      );
    $function$
;

grant delete on table "public"."backup" to "anon";

grant insert on table "public"."backup" to "anon";

grant references on table "public"."backup" to "anon";

grant select on table "public"."backup" to "anon";

grant trigger on table "public"."backup" to "anon";

grant truncate on table "public"."backup" to "anon";

grant update on table "public"."backup" to "anon";

grant delete on table "public"."backup" to "authenticated";

grant insert on table "public"."backup" to "authenticated";

grant references on table "public"."backup" to "authenticated";

grant select on table "public"."backup" to "authenticated";

grant trigger on table "public"."backup" to "authenticated";

grant truncate on table "public"."backup" to "authenticated";

grant update on table "public"."backup" to "authenticated";

grant delete on table "public"."backup" to "service_role";

grant insert on table "public"."backup" to "service_role";

grant references on table "public"."backup" to "service_role";

grant select on table "public"."backup" to "service_role";

grant trigger on table "public"."backup" to "service_role";

grant truncate on table "public"."backup" to "service_role";

grant update on table "public"."backup" to "service_role";

grant delete on table "public"."base2" to "anon";

grant insert on table "public"."base2" to "anon";

grant references on table "public"."base2" to "anon";

grant select on table "public"."base2" to "anon";

grant trigger on table "public"."base2" to "anon";

grant truncate on table "public"."base2" to "anon";

grant update on table "public"."base2" to "anon";

grant delete on table "public"."base2" to "authenticated";

grant insert on table "public"."base2" to "authenticated";

grant references on table "public"."base2" to "authenticated";

grant select on table "public"."base2" to "authenticated";

grant trigger on table "public"."base2" to "authenticated";

grant truncate on table "public"."base2" to "authenticated";

grant update on table "public"."base2" to "authenticated";

grant delete on table "public"."base2" to "service_role";

grant insert on table "public"."base2" to "service_role";

grant references on table "public"."base2" to "service_role";

grant select on table "public"."base2" to "service_role";

grant trigger on table "public"."base2" to "service_role";

grant truncate on table "public"."base2" to "service_role";

grant update on table "public"."base2" to "service_role";

grant delete on table "public"."baseeshows" to "anon";

grant insert on table "public"."baseeshows" to "anon";

grant references on table "public"."baseeshows" to "anon";

grant select on table "public"."baseeshows" to "anon";

grant trigger on table "public"."baseeshows" to "anon";

grant truncate on table "public"."baseeshows" to "anon";

grant update on table "public"."baseeshows" to "anon";

grant delete on table "public"."baseeshows" to "authenticated";

grant insert on table "public"."baseeshows" to "authenticated";

grant references on table "public"."baseeshows" to "authenticated";

grant select on table "public"."baseeshows" to "authenticated";

grant trigger on table "public"."baseeshows" to "authenticated";

grant truncate on table "public"."baseeshows" to "authenticated";

grant update on table "public"."baseeshows" to "authenticated";

grant delete on table "public"."baseeshows" to "service_role";

grant insert on table "public"."baseeshows" to "service_role";

grant references on table "public"."baseeshows" to "service_role";

grant select on table "public"."baseeshows" to "service_role";

grant trigger on table "public"."baseeshows" to "service_role";

grant truncate on table "public"."baseeshows" to "service_role";

grant update on table "public"."baseeshows" to "service_role";

grant delete on table "public"."boletoartistas" to "anon";

grant insert on table "public"."boletoartistas" to "anon";

grant references on table "public"."boletoartistas" to "anon";

grant select on table "public"."boletoartistas" to "anon";

grant trigger on table "public"."boletoartistas" to "anon";

grant truncate on table "public"."boletoartistas" to "anon";

grant update on table "public"."boletoartistas" to "anon";

grant delete on table "public"."boletoartistas" to "authenticated";

grant insert on table "public"."boletoartistas" to "authenticated";

grant references on table "public"."boletoartistas" to "authenticated";

grant select on table "public"."boletoartistas" to "authenticated";

grant trigger on table "public"."boletoartistas" to "authenticated";

grant truncate on table "public"."boletoartistas" to "authenticated";

grant update on table "public"."boletoartistas" to "authenticated";

grant delete on table "public"."boletoartistas" to "service_role";

grant insert on table "public"."boletoartistas" to "service_role";

grant references on table "public"."boletoartistas" to "service_role";

grant select on table "public"."boletoartistas" to "service_role";

grant trigger on table "public"."boletoartistas" to "service_role";

grant truncate on table "public"."boletoartistas" to "service_role";

grant update on table "public"."boletoartistas" to "service_role";

grant delete on table "public"."boletocasas" to "anon";

grant insert on table "public"."boletocasas" to "anon";

grant references on table "public"."boletocasas" to "anon";

grant select on table "public"."boletocasas" to "anon";

grant trigger on table "public"."boletocasas" to "anon";

grant truncate on table "public"."boletocasas" to "anon";

grant update on table "public"."boletocasas" to "anon";

grant delete on table "public"."boletocasas" to "authenticated";

grant insert on table "public"."boletocasas" to "authenticated";

grant references on table "public"."boletocasas" to "authenticated";

grant select on table "public"."boletocasas" to "authenticated";

grant trigger on table "public"."boletocasas" to "authenticated";

grant truncate on table "public"."boletocasas" to "authenticated";

grant update on table "public"."boletocasas" to "authenticated";

grant delete on table "public"."boletocasas" to "service_role";

grant insert on table "public"."boletocasas" to "service_role";

grant references on table "public"."boletocasas" to "service_role";

grant select on table "public"."boletocasas" to "service_role";

grant trigger on table "public"."boletocasas" to "service_role";

grant truncate on table "public"."boletocasas" to "service_role";

grant update on table "public"."boletocasas" to "service_role";

grant delete on table "public"."metas" to "anon";

grant insert on table "public"."metas" to "anon";

grant references on table "public"."metas" to "anon";

grant select on table "public"."metas" to "anon";

grant trigger on table "public"."metas" to "anon";

grant truncate on table "public"."metas" to "anon";

grant update on table "public"."metas" to "anon";

grant delete on table "public"."metas" to "authenticated";

grant insert on table "public"."metas" to "authenticated";

grant references on table "public"."metas" to "authenticated";

grant select on table "public"."metas" to "authenticated";

grant trigger on table "public"."metas" to "authenticated";

grant truncate on table "public"."metas" to "authenticated";

grant update on table "public"."metas" to "authenticated";

grant delete on table "public"."metas" to "service_role";

grant insert on table "public"."metas" to "service_role";

grant references on table "public"."metas" to "service_role";

grant select on table "public"."metas" to "service_role";

grant trigger on table "public"."metas" to "service_role";

grant truncate on table "public"."metas" to "service_role";

grant update on table "public"."metas" to "service_role";

grant delete on table "public"."pessoas" to "anon";

grant insert on table "public"."pessoas" to "anon";

grant references on table "public"."pessoas" to "anon";

grant select on table "public"."pessoas" to "anon";

grant trigger on table "public"."pessoas" to "anon";

grant truncate on table "public"."pessoas" to "anon";

grant update on table "public"."pessoas" to "anon";

grant delete on table "public"."pessoas" to "authenticated";

grant insert on table "public"."pessoas" to "authenticated";

grant references on table "public"."pessoas" to "authenticated";

grant select on table "public"."pessoas" to "authenticated";

grant trigger on table "public"."pessoas" to "authenticated";

grant truncate on table "public"."pessoas" to "authenticated";

grant update on table "public"."pessoas" to "authenticated";

grant delete on table "public"."pessoas" to "service_role";

grant insert on table "public"."pessoas" to "service_role";

grant references on table "public"."pessoas" to "service_role";

grant select on table "public"."pessoas" to "service_role";

grant trigger on table "public"."pessoas" to "service_role";

grant truncate on table "public"."pessoas" to "service_role";

grant update on table "public"."pessoas" to "service_role";



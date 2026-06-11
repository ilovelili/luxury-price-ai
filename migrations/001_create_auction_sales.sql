create table if not exists public.auction_sales (
  id bigserial primary key,
  item_id text not null,
  brand text not null,
  category text,
  shape text,
  rank text,
  title text not null,
  sold_date date,
  price_jpy integer not null check (price_jpy >= 0),
  item_url text,
  image_url text,
  auction text,
  source_month text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (item_id)
);

create index if not exists auction_sales_brand_category_shape_idx
  on public.auction_sales (brand, category, shape);

create index if not exists auction_sales_rank_idx
  on public.auction_sales (rank);

create index if not exists auction_sales_sold_date_idx
  on public.auction_sales (sold_date desc);

create index if not exists auction_sales_price_idx
  on public.auction_sales (price_jpy);

alter table public.auction_sales enable row level security;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_auction_sales_updated_at on public.auction_sales;
create trigger set_auction_sales_updated_at
before update on public.auction_sales
for each row execute function public.set_updated_at();

begin;

alter table public.crm_accounts
  drop constraint crm_accounts_organization_id_domain_key;

create unique index crm_accounts_org_domain_unique_idx
  on public.crm_accounts (organization_id, domain)
  where domain is not null;

commit;

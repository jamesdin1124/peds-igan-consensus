-- Meeting issues shown under each statement, and each member's preference.
create table if not exists public.issues (
  id text primary key,
  ord integer not null default 0,
  tag text not null default '',
  topic text not null default '',
  question text not null,
  options jsonb not null default '[]'::jsonb,
  note text not null default '',
  rec_codes text[] not null default '{}'
);
create table if not exists public.issue_votes (
  issue_id text not null references public.issues(id) on delete cascade,
  voter_email text not null default lower(auth.jwt() ->> 'email'),
  choice text,
  comment text not null default '',
  updated_at timestamptz not null default now(),
  primary key (issue_id, voter_email)
);
alter table public.issues enable row level security;
alter table public.issue_votes enable row level security;

create policy issues_read on public.issues for select using (public.is_member());
create policy issues_admin_ins on public.issues for insert with check (public.is_admin());
create policy issues_admin_upd on public.issues for update using (public.is_admin()) with check (public.is_admin());
create policy issues_admin_del on public.issues for delete using (public.is_admin());

create policy issue_votes_read_own on public.issue_votes for select using (voter_email = public.my_email() or public.is_admin());
create policy issue_votes_ins_own on public.issue_votes for insert with check (public.is_member() and voter_email = public.my_email());
create policy issue_votes_upd_own on public.issue_votes for update using (voter_email = public.my_email()) with check (public.is_member() and voter_email = public.my_email());
create policy issue_votes_del_own on public.issue_votes for delete using (voter_email = public.my_email());

-- Same blind rule as round_summary: members see nothing until results are published; managers always see.
create or replace function public.issue_summary()
returns jsonb language plpgsql stable security definer set search_path to '' as $$
declare result jsonb;
begin
  if not public.is_member() then raise exception 'not a committee member'; end if;
  if not public.is_admin() and not coalesce((select c.results_public from public.config c where c.id = 1), false) then
    return '{}'::jsonb;
  end if;
  select coalesce(jsonb_object_agg(s.issue_id, s.payload), '{}'::jsonb) into result
  from (
    select v.issue_id, jsonb_build_object(
      'counts', coalesce((select jsonb_object_agg(x.choice, x.n) from (select v2.choice, count(*) n from public.issue_votes v2 where v2.issue_id = v.issue_id and coalesce(v2.choice,'') <> '' group by v2.choice) x), '{}'::jsonb),
      'comments', coalesce((select jsonb_agg(jsonb_build_object('name', coalesce(nullif(m.display_name,''), split_part(v3.voter_email,'@',1)), 'choice', v3.choice, 'comment', v3.comment) order by v3.updated_at)
                  from public.issue_votes v3 left join public.members m on m.email = v3.voter_email
                  where v3.issue_id = v.issue_id and v3.comment <> ''), '[]'::jsonb)
    ) as payload
    from public.issue_votes v group by v.issue_id
  ) s;
  return result;
end $$;
revoke all on function public.issue_summary() from public, anon;
grant execute on function public.issue_summary() to authenticated;

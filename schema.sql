-- =====================================================================
-- PASSAGE — CORE DATA MODEL (PostgreSQL 15+)
-- Phase 1 deliverable: Universities / Programs / Scholarships / Requirements / FeeStructures
-- plus the surrounding tables needed by the rest of the platform.
--
-- Conventions:
--   - uuid primary keys (gen_random_uuid(), from pgcrypto)
--   - created_at / updated_at on every mutable table
--   - money stored as integer cents to avoid float rounding errors
--   - enums kept narrow; anything open-ended (waiver criteria, requirement
--     detail) goes in jsonb so the Catalog Agent can extend it without a
--     migration every time a new portal quirk shows up
-- =====================================================================

create extension if not exists pgcrypto;
create extension if not exists "uuid-ossp";
-- Optional: if you want RAG matching to live in Postgres instead of a
-- separate vector DB, enable pgvector and see the note at the bottom.
-- create extension if not exists vector;

-- ---------------------------------------------------------------------
-- ENUMS
-- ---------------------------------------------------------------------
create type degree_level as enum ('undergraduate','transfer','graduate','master','phd');
create type fee_status   as enum ('zero_fee','fee_waiver_available','fee_required');
create type app_status   as enum (
  'matched','sop_tailoring','staged_awaiting_user','submitted',
  'action_required','decision_received','withdrawn'
);
create type req_type     as enum (
  'transcript','test_score','essay','recommendation_letter',
  'passport','financial_proof','portfolio','interview','other'
);

-- ---------------------------------------------------------------------
-- CATALOG: Universities, Programs, Scholarships
-- ---------------------------------------------------------------------
create table universities (
  id                uuid primary key default gen_random_uuid(),
  name              text not null,
  country           text not null,
  region            text not null,               -- North America | Europe | Eastern Europe | Asia
  portal_system     text,                          -- 'common_app' | 'ucas' | 'uni_assist' | 'studielink' | 'custom' ...
  portal_url        text,
  website            text,
  logo_url          text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index idx_universities_region on universities(region);

create table fields_of_study (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique not null,     -- e.g. 'ai-ml', matches the taxonomy used in the Find Programs UI
  category    text not null,            -- Technology & Computing | Healthcare & Life Sciences | ...
  name        text not null,
  description text
);

create table programs (
  id                 uuid primary key default gen_random_uuid(),
  university_id      uuid not null references universities(id) on delete cascade,
  field_of_study_id  uuid not null references fields_of_study(id),
  name               text not null,                 -- "MSc Computer Science"
  degree_level       degree_level not null,
  language           text default 'English',
  duration_months    int,
  application_deadline date,
  intake_term        text,                            -- 'Fall 2027', 'Spring 2027'
  fee_status         fee_status not null default 'fee_required',
  application_fee_cents int default 0,
  currency           text default 'USD',
  source_url         text,                            -- where the Catalog Agent last verified this
  last_verified_at   timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create index idx_programs_university on programs(university_id);
create index idx_programs_field on programs(field_of_study_id);
create index idx_programs_deadline on programs(application_deadline);
create index idx_programs_fee_status on programs(fee_status);

create table scholarships (
  id                uuid primary key default gen_random_uuid(),
  name              text not null,                    -- "DAAD AI & Data Science Scholarships"
  provider          text,                              -- "DAAD", "Fulbright Commission" ...
  country           text,
  covers            text,                              -- "Full tuition + stipend"
  eligibility_notes text,
  application_url   text,
  deadline          date,
  created_at        timestamptz not null default now()
);

-- many-to-many: a scholarship can apply to several programs, a program can
-- have several scholarship options
create table program_scholarships (
  program_id     uuid not null references programs(id) on delete cascade,
  scholarship_id uuid not null references scholarships(id) on delete cascade,
  primary key (program_id, scholarship_id)
);

-- ---------------------------------------------------------------------
-- Requirements & Fee Structures
-- (kept separate from `programs` so the Pre-Flight Checker can query
-- them independently and so waiver logic doesn't bloat the programs row)
-- ---------------------------------------------------------------------
create table requirements (
  id           uuid primary key default gen_random_uuid(),
  program_id   uuid not null references programs(id) on delete cascade,
  type         req_type not null,
  description  text not null,             -- "Certified apostille translation of diploma"
  is_mandatory boolean not null default true,
  min_score    numeric,                    -- e.g. IELTS 6.5 minimum, nullable for non-test reqs
  metadata     jsonb default '{}'::jsonb   -- portal-specific quirks the Catalog Agent discovers
);
create index idx_requirements_program on requirements(program_id);

create table fee_structures (
  id                 uuid primary key default gen_random_uuid(),
  program_id         uuid not null references programs(id) on delete cascade,
  fee_status         fee_status not null,
  amount_cents       int default 0,
  currency           text default 'USD',
  waiver_criteria    jsonb default '{}'::jsonb,
  -- example waiver_criteria payload:
  -- {"income_threshold_usd": 30000, "eligible_countries": ["NG","IN","PH"],
  --  "early_submission_days_before_deadline": 30, "institutional_code": "PASSAGE24"}
  waiver_requires_self_attestation boolean not null default true,
  created_at         timestamptz not null default now()
);
create index idx_fee_structures_program on fee_structures(program_id);

-- ---------------------------------------------------------------------
-- STUDENTS & VAULT
-- ---------------------------------------------------------------------
create table students (
  id               uuid primary key default gen_random_uuid(),
  email            text unique not null,
  full_name        text not null,
  auth_provider    text not null default 'password',   -- 'google' | 'password'
  proxy_email      text unique,                          -- app_<id>@applybridge.com — student-controlled alias, not a silent intercept
  fee_strategy     text not null default 'hybrid_smart_tiering',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create table student_documents (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid not null references students(id) on delete cascade,
  doc_type      req_type not null,
  file_url      text not null,
  ocr_status    text not null default 'pending',     -- pending | parsed | failed
  parsed_data   jsonb default '{}'::jsonb,             -- extracted fields from the Ingestion Agent
  uploaded_at   timestamptz not null default now()
);

create table gpa_conversions (
  id                uuid primary key default gen_random_uuid(),
  student_document_id uuid not null references student_documents(id) on delete cascade,
  original_scale    text not null,        -- "100-point"
  original_value    numeric not null,
  us_4_0            numeric,
  ects_grade        text,
  german_scale      numeric,
  uk_honours        text,
  computed_at       timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- REFEREES (Letters of Recommendation)
-- ---------------------------------------------------------------------
create table referees (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid not null references students(id) on delete cascade,
  name          text not null,
  email         text not null,
  relationship  text,                       -- "Thesis advisor", "Line manager"
  status        text not null default 'not_sent',  -- not_sent | sent | viewed | uploaded
  upload_link_token uuid not null default gen_random_uuid(),
  reminder_count int not null default 0,
  created_at    timestamptz not null default now()
);

create table referee_documents (
  id            uuid primary key default gen_random_uuid(),
  referee_id    uuid not null references referees(id) on delete cascade,
  file_url      text not null,
  applies_to_program_ids uuid[] default '{}',
  uploaded_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- ESSAYS / SOP DRAFTING
-- ---------------------------------------------------------------------
create table essays (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid not null references students(id) on delete cascade,
  program_id    uuid references programs(id),
  essay_type    text not null default 'sop',   -- sop | motivation_letter | cv | lor_draft
  draft_text    text,
  student_edited_text text,
  status        text not null default 'drafted',  -- drafted | student_editing | approved
  originality_check_pct numeric,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- APPLICATIONS & STATUS HISTORY
-- ---------------------------------------------------------------------
create table applications (
  id              uuid primary key default gen_random_uuid(),
  student_id      uuid not null references students(id) on delete cascade,
  program_id      uuid not null references programs(id),
  status          app_status not null default 'matched',
  essay_id        uuid references essays(id),
  fee_charge_id   uuid,                       -- fk to wallet_transactions, added below
  staged_form_snapshot jsonb,                  -- what the co-pilot pre-filled, shown to student before submit
  submitted_at    timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (student_id, program_id)
);
create index idx_applications_student on applications(student_id);
create index idx_applications_status on applications(status);

create table application_events (
  id             uuid primary key default gen_random_uuid(),
  application_id uuid not null references applications(id) on delete cascade,
  event_type     text not null,   -- 'matched' | 'sop_drafted' | 'staged' | 'submitted' | 'email_received' | 'decision'
  detail         jsonb default '{}'::jsonb,
  occurred_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- WALLET (Stripe Issuing-backed virtual cards)
-- ---------------------------------------------------------------------
create table wallets (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid unique not null references students(id) on delete cascade,
  balance_cents int not null default 0,
  currency      text not null default 'USD',
  updated_at    timestamptz not null default now()
);

create table wallet_transactions (
  id               uuid primary key default gen_random_uuid(),
  wallet_id        uuid not null references wallets(id) on delete cascade,
  application_id   uuid references applications(id),
  type             text not null,        -- 'top_up' | 'application_fee' | 'waiver_no_charge' | 'refund'
  amount_cents     int not null,
  stripe_card_id   text,                  -- Stripe Issuing single-use card reference
  user_confirmed_at timestamptz,          -- null until the student taps confirm — nothing charges before this
  created_at       timestamptz not null default now()
);
alter table applications add constraint fk_fee_charge foreign key (fee_charge_id) references wallet_transactions(id);

-- ---------------------------------------------------------------------
-- INBOX (student-controlled alias, not a covert intercept)
-- ---------------------------------------------------------------------
create table inbox_messages (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid not null references students(id) on delete cascade,
  application_id uuid references applications(id),
  from_address  text not null,
  subject       text,
  body_raw      text,
  category      text,        -- 'missing_document' | 'interview_invite' | 'decision' | 'fee_confirmation' | 'other'
  suggested_reply text,       -- drafted for the student; student sends it, agent never auto-sends
  student_sent_at timestamptz,
  received_at   timestamptz not null default now()
);

-- =====================================================================
-- NOTES ON THE VECTOR-SEARCH SIDE (program matching / RAG)
-- =====================================================================
-- The Global Catalog & Matching Agent needs semantic search over program
-- descriptions, research focus areas, and student profiles. Two options:
--
-- 1) Separate vector DB (Qdrant / Pinecone) — recommended once catalog
--    size grows past ~50k programs or you need managed scaling:
--      collection: program_embeddings
--      payload:    { program_id: uuid, university: text, field: text,
--                    degree_level: text, region: text, fee_status: text }
--      vector:     embedding of "<program name> — <description> —
--                   <research focus areas>" (1536-dim, text-embedding-3-large
--                   or similar)
--    The vector DB stores program_id as payload and Postgres stays the
--    source of truth for everything transactional.
--
-- 2) pgvector in this same database — simpler ops, fine up to a few
--    hundred thousand rows:
--
--    create extension if not exists vector;
--    alter table programs add column embedding vector(1536);
--    create index on programs using ivfflat (embedding vector_cosine_ops);
--
--    Match query sketch:
--    select id, name from programs
--    order by embedding <=> $1::vector
--    limit 20;
--
-- Student-side matching input is built from: field_of_study selection,
-- degree_level, target regions, fee_strategy, and a short embedding of
-- the student's stated goals/background collected during onboarding.
-- =====================================================================

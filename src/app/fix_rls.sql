-- SCRIPT DE CORREÇÃO DE SEGURANÇA RLS
-- RH CONNECT

-- 1. Tabela: Recruiters
ALTER TABLE public.recruiters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir tudo para recruiters" ON public.recruiters;
-- Somente o Service Role (backend) deve gerenciar recrutadores se usarmos Custom Auth
-- Nenhuma política pública é necessária.

-- 2. Tabela: Clients
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir tudo para clients" ON public.clients;
-- Somente o Service Role gerencia clientes. Nenhuma política pública.

-- 3. Tabela: Jobs
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir tudo para jobs" ON public.jobs;
-- Público pode ver as vagas
CREATE POLICY "Qualquer pessoa pode ver vagas" 
ON public.jobs FOR SELECT 
TO anon, authenticated 
USING (true);
-- Escrita bloqueada para público.

-- 4. Tabela: Candidates
ALTER TABLE public.candidates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir tudo para candidates" ON public.candidates;
-- Público pode se inscrever (INSERT)
CREATE POLICY "Candidatos podem se inscrever" 
ON public.candidates FOR INSERT 
TO anon, authenticated 
WITH CHECK (true);
-- Leitura e edição bloqueadas para público.

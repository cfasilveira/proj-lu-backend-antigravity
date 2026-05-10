-- Adicionar coluna de status de contratação
ALTER TABLE public.candidates 
ADD COLUMN IF NOT EXISTS hired BOOLEAN DEFAULT FALSE;

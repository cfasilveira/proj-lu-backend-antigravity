import asyncio
import sys
from app.database import get_supabase
from app.services.ai_service import score_candidate

async def repair(force=True):
    print("🛠️ Iniciando REPROCESSAMENTO COMPLETO (Force) com a Nova Chave...", flush=True)
    supabase = get_supabase()
    
    # Buscar todos os candidatos
    res = supabase.table('candidates').select('id, name, resume_text, job_id, ai_justification').execute()
    candidates = res.data
    
    if not candidates:
        print("✅ Nenhum candidato encontrado.")
        return

    print(f"🔍 Reprocessando {len(candidates)} candidatos para testar a nova cota.", flush=True)
    print("⏳ Intervalo de 6 segundos entre análises...", flush=True)

    for i, cand in enumerate(candidates):
        # Buscar descrição da vaga
        job_res = supabase.table('jobs').select('description').eq('id', cand['job_id']).single().execute()
        job_description = job_res.data['description']
        
        print(f"  [{i+1}/{len(candidates)}] Analisando {cand['name']}...", flush=True)
        
        # Chamar IA Real (com a nova chave no .env carregada pelo backend)
        analysis = await score_candidate(cand['resume_text'], job_description)
        
        if analysis.get("score", 0) > 0:
            # Atualizar no banco
            supabase.table('candidates').update({
                "ai_score": analysis.get("score", 0),
                "ai_justification": analysis.get("summary", ""),
                "ai_strengths": analysis.get("strengths", []),
                "ai_weaknesses": analysis.get("weaknesses", [])
            }).eq('id', cand['id']).execute()
            print(f"    ✅ Sucesso! Score: {analysis['score']}%", flush=True)
        else:
            print(f"    ❌ Falha: {analysis.get('summary')}", flush=True)
        
        # Delay de segurança (6 segundos é o limite ideal para 15 RPM)
        if i < len(candidates) - 1:
            await asyncio.sleep(6)

    print("\n✨ Reprocessamento concluído! Todos os perfis foram testados com a nova API Key.")

if __name__ == "__main__":
    asyncio.run(repair())

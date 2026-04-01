import asyncio
import random
from app.database import get_supabase
from app.services.ai_service import score_candidate

# Dados detalhados de Vagas
DETAILED_JOBS = [
    {
        "title": "Desenvolvedor Full Stack Sênior (Node.js & React)",
        "uf": "SP", "city": "São Paulo", "salary": 16000, "type": "Remoto",
        "description": "Buscamos um desenvolvedor com 5+ anos de experiência. Requisitos: TypeScript, Node.js, React, PostgreSQL, AWS (S3, Lambda, EC2). Diferencial: Docker, Kubernetes, Scrum."
    },
    {
        "title": "Analista de Dados Pleno",
        "uf": "RJ", "city": "Rio de Janeiro", "salary": 8500, "type": "Híbrido",
        "description": "Criação de dashboards em Power BI ou Tableau. Extração de dados via SQL e Python (Pandas/NumPy). Requisitos: SQL, Python, Excel Avançado."
    },
    {
        "title": "Gerente de Marketing Digital",
        "uf": "MG", "city": "Belo Horizonte", "salary": 11000, "type": "Presencial",
        "description": "Foco em aquisição (SEO/SEM). Gestão de tráfego pago (Google Ads/Meta Ads), GA4. Necessário Inglês Avançado."
    },
    {
        "title": "Engenheiro de DevOps",
        "uf": "PR", "city": "Curitiba", "salary": 14500, "type": "Remoto",
        "description": "Foco em CI/CD, Terraform, Ansible, Jenkins, Azure. Monitoramento (Prometheus, Grafana)."
    }
]

# Perfil detalhados dos candidatos para avaliação real
CANDIDATE_DATA = [
    {
        "name": "Alexandre Silva",
        "resume": "Desenvolvedor Senior com 8 anos de experiência em stacks JS/TS. Expert em Node.js e React. Experiência avançada em AWS (Lambda, S3, RDS). Conhecimento profundo em SOLID e Clean Architecture.",
        "uf": "SP", "gender": "M"
    },
    {
        "name": "Beatriz Santos",
        "resume": "Analista de Dados com 3 anos de experiência. Domínio absoluto de SQL e Python para ETL. Criei dashboards em Power BI para grandes redes de varejo. Conhecimento em estatística aplicada.",
        "uf": "RJ", "gender": "F"
    },
    {
        "name": "Claudio Oliveira",
        "resume": "Gerente de Marketing com 10 anos de experiência. Especialista em Google Ads e Meta Ads com certificação. Inglês fluente. Vivência em gestão de orçamentos acima de 100k/mês.",
        "uf": "MG", "gender": "M"
    },
    {
        "name": "Daniela Lima",
        "resume": "Especialista em DevOps. Domínio de Terraform, Docker e Kubernetes. Experiência em migração para Azure e implementação de pipelines CI/CD com Jenkins. Monitoramento via Prometheus.",
        "uf": "PR", "gender": "F"
    },
    {
        "name": "Eduardo Souza",
        "resume": "Desenvolvedor Junior. Conheço React e estou aprendendo Node.js. Fiz alguns projetos acadêmicos e um curso na Udemy sobre AWS.",
        "uf": "SP", "gender": "M"
    },
    {
        "name": "Fernanda Ferreira",
        "resume": "Analista de Suporte com interesse em Dados. Conheço Excel avançado e estou estudando SQL por conta própria.",
        "uf": "BA", "gender": "F"
    },
    {
        "name": "Gabriel Rocha",
        "resume": "Vendedor com experiência em varejo. Estou mudando de área para Marketing Digital. Fiz um curso de SEO de 20 horas.",
        "uf": "RS", "gender": "M"
    },
    {
        "name": "Helena Costa",
        "resume": "Arquiteta de Cloud (AWS). 12 anos de TI. Especialista em segurança e escalabilidade. Experiência com Terraform e governança de cloud.",
        "uf": "SP", "gender": "F"
    }
]

async def seed():
    print("🧹 Resetando banco para dados de ALTA FIDELIDADE...", flush=True)
    supabase = get_supabase()
    
    # Limpar candidatos antes de vagas
    supabase.table('candidates').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    supabase.table('jobs').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    
    # Get Recruiter ID
    recruiter = supabase.table('recruiters').select('id').eq('email', 'admin@rhconnect.com').single().execute()
    recruiter_id = recruiter.data['id']

    # Inserir 4 vagas detalhadas
    inserted_jobs = []
    for j in DETAILED_JOBS:
        res = supabase.table('jobs').insert({**j, "recruiter_id": recruiter_id}).execute()
        inserted_jobs.append(res.data[0])
    
    print(f"✅ {len(inserted_jobs)} vagas de alta qualidade inseridas.", flush=True)
    print("🚀 Gerando 15 candidatos com análise REAL do Gemini 2.0 (com delay para evitar 429)...", flush=True)

    for i in range(15):
        # Selecionar um perfil de candidato e uma vaga
        profile = random.choice(CANDIDATE_DATA)
        job = random.choice(inserted_jobs)
        
        cand_name = f"{profile['name']} (Teste {i+1})"
        print(f"  [{i+1}/15] Analisando {cand_name} para {job['title']}...", flush=True)
        
        # Chamar IA Real
        analysis = await score_candidate(profile['resume'], job['description'])
        
        # Salvar no DB
        supabase.table('candidates').insert({
            "job_id": job['id'],
            "name": cand_name,
            "email": f"teste.{i+1}.qa@exemplo.com",
            "gender": profile['gender'],
            "uf": profile['uf'],
            "resume_text": profile['resume'],
            "ai_score": analysis.get("score", 0),
            "ai_justification": analysis.get("summary", "Análise não disponível."),
            "cpf_encrypted": "MOCK_CPF"
        }).execute()
        
        # Aguardar 4 segundos para evitar Rate Limit da API Gratuita
        await asyncio.sleep(4)

    print("\n✨ Missão cumprida! Dados de alta fidelidade prontos no dashboard.")

if __name__ == "__main__":
    asyncio.run(seed())

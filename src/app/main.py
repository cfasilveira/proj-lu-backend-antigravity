from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import bcrypt

from .database import get_supabase
from .services.pdf_service import extract_text_from_pdf
from .services.ai_service import score_candidate

app = FastAPI(title="RH Connect API")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schemas ---

class JobCreate(BaseModel):
    title: str
    description: str
    salary: float
    city: str
    uf: str
    type: str
    recruiter_id: str

class RecruiterLogin(BaseModel):
    email: str
    password: str

# --- Auth Routes ---

@app.post("/auth/signup")
async def signup(recruiter: RecruiterLogin):
    supabase = get_supabase()
    # Hash da senha
    hashed = bcrypt.hashpw(recruiter.password.encode(), bcrypt.gensalt()).decode()
    
    new_recruiter = {
        "email": recruiter.email,
        "password_hash": hashed,
        "name": recruiter.email.split('@')[0]
    }
    
    try:
        response = supabase.table("recruiters").insert(new_recruiter).execute()
        return response.data[0]
    except Exception:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

@app.post("/auth/login")
async def login(credentials: RecruiterLogin):
    supabase = get_supabase()
    response = supabase.table("recruiters").select("*").eq("email", credentials.email).execute()
    
    if not response.data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
        
    user = response.data[0]
    if bcrypt.checkpw(credentials.password.encode(), user['password_hash'].encode()):
        return {"id": user['id'], "email": user['email'], "name": user['name']}
    
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

# --- Job Routes ---

@app.get("/jobs")
async def get_jobs():
    supabase = get_supabase()
    response = supabase.table("jobs").select("*").order("created_at", desc=True).execute()
    return response.data

@app.post("/jobs")
async def create_job(job: JobCreate):
    supabase = get_supabase()
    response = supabase.table("jobs").insert(job.model_dump()).execute()
    return response.data[0]

@app.put("/jobs/{job_id}")
async def update_job(job_id: str, job: JobCreate):
    supabase = get_supabase()
    response = supabase.table("jobs").update(job.model_dump()).eq("id", job_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    return response.data[0]

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    supabase = get_supabase()
    supabase.table("jobs").delete().eq("id", job_id).execute()
    return {"message": "Vaga deletada"}

# --- Background Task: Análise de IA ---

async def process_ai_analysis(candidate_id: str, resume_text: str, job_desc: str):
    """Roda em background: analisa o currículo e atualiza o candidato no banco."""
    supabase = get_supabase()
    try:
        ai_result = await score_candidate(resume_text, job_desc)
        supabase.table("candidates").update({
            "ai_score": ai_result.get("score", 0),
            "ai_justification": ai_result.get("summary", ""),
            "ai_strengths": ai_result.get("strengths", []),
            "ai_weaknesses": ai_result.get("weaknesses", []),
        }).eq("id", candidate_id).execute()
        print(f"✅ Análise IA concluída para candidato {candidate_id}: score={ai_result.get('score', 0)}")
    except Exception as e:
        print(f"❌ Erro na análise IA em background para {candidate_id}: {e}")
        supabase.table("candidates").update({
            "ai_justification": f"Erro na análise automática: {str(e)}"
        }).eq("id", candidate_id).execute()

# --- Candidate Routes ---

@app.post("/candidates", status_code=201)
async def register_candidate(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    gender: str = Form(...),
    uf: str = Form(...),
    cpf: str = Form(...),
    resume_text: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None)
):
    supabase = get_supabase()
    
    job_res = supabase.table("jobs").select("description").eq("id", job_id).single().execute()
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    job_desc = job_res.data['description']
    
    final_resume_text = resume_text or ""
    if resume_file:
        file_bytes = await resume_file.read()
        final_resume_text = extract_text_from_pdf(file_bytes)
    
    # Salva o candidato IMEDIATAMENTE com score pendente
    new_candidate = {
        "job_id": job_id,
        "name": name,
        "email": email,
        "gender": gender,
        "uf": uf,
        "resume_text": final_resume_text,
        "ai_score": 0,
        "ai_justification": "Análise em andamento...",
        "cpf_encrypted": cpf
    }
    
    response = supabase.table("candidates").insert(new_candidate).execute()
    saved_candidate = response.data[0]
    
    # Dispara a análise da IA em background (não bloqueia a resposta)
    background_tasks.add_task(
        process_ai_analysis,
        saved_candidate["id"],
        final_resume_text,
        job_desc
    )
    
    return saved_candidate

@app.get("/candidates")
async def get_candidates(job_id: Optional[str] = None):
    supabase = get_supabase()
    query = supabase.table("candidates").select("*")
    if job_id:
        query = query.eq("job_id", job_id)
    response = query.order("ai_score", desc=True).execute()
    return response.data

@app.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str):
    supabase = get_supabase()
    supabase.table("candidates").delete().eq("id", candidate_id).execute()
    return {"message": "Candidato removido"}

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import bcrypt
import traceback
import re
from fastapi.responses import JSONResponse
from fastapi.requests import Request

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

# --- Exception Handlers for CORS Resilience ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"❌ Erro Global: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno no servidor", "error": str(exc)},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
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
    client_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ClientCreate(BaseModel):
    name: str

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

# --- Client Routes ---

@app.get("/clients")
async def get_clients():
    supabase = get_supabase()
    response = supabase.table("clients").select("*").order("name").execute()
    return response.data

@app.post("/clients")
async def create_client(client: ClientCreate):
    supabase = get_supabase()
    response = supabase.table("clients").insert(client.model_dump()).execute()
    return response.data[0]

# --- Job Routes ---

@app.get("/jobs")
async def get_jobs():
    supabase = get_supabase()
    # Puxa todas as vagas e inclui o nome do cliente vinculado
    response = supabase.table("jobs").select("*, clients(name)").order("created_at", desc=True).execute()
    
    # Formata a resposta para facilitar o frontend
    jobs = []
    for row in response.data:
        client_data = row.pop("clients", None)
        row["client_name"] = client_data["name"] if client_data else "Cliente Padrão"
        jobs.append(row)
        
    return jobs

@app.post("/jobs")
async def create_job(job: JobCreate):
    supabase = get_supabase()
    response = supabase.table("jobs").insert(job.model_dump()).execute()
    row = response.data[0]
    
    # Busca o nome do cliente separadamente
    client_res = supabase.table("clients").select("name").eq("id", job.client_id).execute()
    if client_res.data:
        row["client_name"] = client_res.data[0]["name"]
    else:
        row["client_name"] = "Cliente Padrão"
        
    return row

@app.put("/jobs/{job_id}")
async def update_job(job_id: str, job: JobCreate):
    supabase = get_supabase()
    response = supabase.table("jobs").update(job.model_dump()).eq("id", job_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    row = response.data[0]
    
    # Busca o nome do cliente separadamente
    client_res = supabase.table("clients").select("name").eq("id", job.client_id).execute()
    if client_res.data:
        row["client_name"] = client_res.data[0]["name"]
    else:
        row["client_name"] = "Cliente Padrão"
        
    return row

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
        if not job_desc:
            supabase.table("candidates").update({
                "ai_score": 0,
                "ai_justification": "Candidato no Banco de Talentos. Análise de adequação genérica (não vinculada a vaga específica).",
                "ai_strengths": ["Análise geral não implementada"],
                "ai_weaknesses": ["Análise geral não implementada"],
            }).eq("id", candidate_id).execute()
            return

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

def mask_cpf(cpf: str) -> str:
    """Mascaramento básico de CPF para privacidade: 123.456.789-01 -> 123.***.***-01"""
    clean_cpf = "".join(filter(str.isdigit, cpf))
    if len(clean_cpf) != 11:
        return cpf # Retorna original se não for um CPF válido
    return f"{clean_cpf[:3]}.***.***-{clean_cpf[-2:]}"

@app.post("/candidates", status_code=201)
async def register_candidate(
    background_tasks: BackgroundTasks,
    job_id: Optional[str] = Form(None),
    name: str = Form(...),
    email: str = Form(...),
    gender: str = Form(...),
    uf: str = Form(...),
    cpf: str = Form(...),
    salary_expectation: float = Form(..., ge=0),
    resume_text: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None)
):
    # Validações rígidas de Backend
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        raise HTTPException(status_code=400, detail="Formato de E-mail inválido.")
        
    clean_cpf = "".join(filter(str.isdigit, cpf))
    if len(clean_cpf) != 11:
        raise HTTPException(status_code=400, detail="CPF inválido. Deve conter exatamente 11 dígitos numéricos.")

    supabase = get_supabase()
    
    job_desc = ""
    if job_id and job_id != "banco-talento":
        job_res = supabase.table("jobs").select("description").eq("id", job_id).single().execute()
        if not job_res.data:
            raise HTTPException(status_code=404, detail="Vaga não encontrada")
        job_desc = job_res.data['description']
    else:
        job_id = None # Set to None for Banco de Talentos
    
    final_resume_text = resume_text or ""
    if resume_file:
        file_bytes = await resume_file.read()
        final_resume_text = extract_text_from_pdf(file_bytes)
    
    # Salva o candidato IMEDIATAMENTE com score pendente e CPF mascarado
    new_candidate = {
        "job_id": job_id,
        "name": name,
        "email": email,
        "gender": gender,
        "uf": uf,
        "resume_text": final_resume_text,
        "ai_score": 0,
        "ai_justification": "Análise em andamento...",
        "cpf_encrypted": mask_cpf(cpf),
        "salary_expectation": salary_expectation
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
    
    # Renomeia cpf_encrypted para cpf para o frontend e decodifica se for hex
    candidates = []
    for c in response.data:
        cpf_val = c.pop("cpf_encrypted", None)
        if cpf_val:
            # Caso 1: Já é bytes (alguns drivers retornam assim)
            if isinstance(cpf_val, bytes):
                try:
                    c["cpf"] = cpf_val.decode('utf-8')
                except:
                    c["cpf"] = str(cpf_val)
            # Caso 2: É uma string hex formatada pelo Postgres (\x...)
            elif isinstance(cpf_val, str) and (cpf_val.startswith("\\x") or cpf_val.startswith(r"\x")):
                try:
                    # Remove o prefixo \x ou \\x
                    hex_str = cpf_val[2:] if cpf_val.startswith(r"\x") else cpf_val[2:]
                    c["cpf"] = bytes.fromhex(hex_str).decode('utf-8')
                except:
                    c["cpf"] = cpf_val
            else:
                c["cpf"] = str(cpf_val)
        else:
            c["cpf"] = c.get("cpf", "-")
            
        candidates.append(c)
        
    return candidates

@app.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str):
    supabase = get_supabase()
    supabase.table("candidates").delete().eq("id", candidate_id).execute()
    return {"message": "Candidato removido"}

class CandidateUpdate(BaseModel):
    notes: Optional[str] = None
    whatsapp_sent: Optional[bool] = None
    hired: Optional[bool] = None

@app.put("/candidates/{candidate_id}")
async def update_candidate(candidate_id: str, updates: CandidateUpdate):
    supabase = get_supabase()
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_data:
        return {"message": "Nenhuma alteração enviada"}
        
    response = supabase.table("candidates").update(update_data).eq("id", candidate_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    return response.data[0]

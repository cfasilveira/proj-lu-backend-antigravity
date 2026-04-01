import json
import httpx
from ..database import settings

async def score_with_gemini(resume_text: str, job_description: str):
    """Lógica original usando Google Gemini"""
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    Você é um recrutador técnico especialista. Analise o currículo abaixo em relação aos requisitos da vaga.
    
    REQUISITOS DA VAGA:
    {job_description}
    
    CURRÍCULO DO CANDIDATO:
    {resume_text}
    
    Forneça uma análise estruturada em formato JSON com os seguintes campos:
    - score: Um número inteiro de 0 a 100 representando a aderência.
    - summary: Um texto curto (máximo 4 linhas) justificando a nota de forma profissional, destacando pontos fortes e lacunas.
    
    Responda APENAS o JSON puro, sem formatação markdown ou blocos de código.
    """
    
    response = await model.generate_content_async(prompt)
    text = response.text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
        
    return json.loads(text)

async def score_with_ollama(resume_text: str, job_description: str):
    """Lógica usando Ollama local (Mistral-Nemo ou similar)"""
    url = f"{settings.ollama_url}/api/generate"
    
    prompt = f"""
    Analise o currículo para a vaga abaixo.
    Retorne APENAS um JSON no formato: {{"score": valor_0_a_100, "summary": "justificativa_curta"}}
    
    Vaga: {job_description}
    Currículo: {resume_text}
    """
    
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        return json.loads(result['response'])

async def score_candidate(resume_text: str, job_description: str):
    """Dispatcher principal baseado nas configurações do .env"""
    try:
        if settings.ai_provider == "ollama":
            print(f"🤖 Usando Provedor Local: {settings.ollama_model}")
            return await score_with_ollama(resume_text, job_description)
        else:
            print("☁️ Usando Provedor Nuvem: Gemini 2.0 Flash")
            return await score_with_gemini(resume_text, job_description)
    except Exception as e:
        print(f"❌ Erro no Provedor {settings.ai_provider}: {e}")
        return {
            "score": 0,
            "summary": f"Erro ao processar análise da IA ({settings.ai_provider}): {str(e)}"
        }

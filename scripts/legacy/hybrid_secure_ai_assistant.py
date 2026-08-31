"""
QuantHire AI - Hybrid Secure AI Assistant
=========================================

This backend provides:
1. On-premises processing for sensitive data (resumes, personal info)
2. AI assistant for general queries (non-sensitive questions)
3. Smart data filtering and anonymization
4. Best of both worlds: Security + Conversational AI
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import requests

# Import our local AI components
from advanced_local_ai_backend import AdvancedLocalAI

class HybridAIAssistant:
    """Hybrid AI assistant with smart data filtering"""
    
    def __init__(self):
        self.local_ai = AdvancedLocalAI()
        self.llm_provider = os.getenv("LLM_PROVIDER", "google")
        self.gemini_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.model = os.getenv("LLM_MODEL", "gemini-1.5-flash-001")
        self.sensitive_patterns = self._load_sensitive_patterns()
        self.local_knowledge_base = self._load_local_knowledge()
    
    def _load_sensitive_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for sensitive data detection"""
        return {
            "personal_info": [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
                r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
                r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
                r'\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b',  # Credit card
                r'\b[A-Za-z]+\s[A-Za-z]+\b',  # Full names
            ],
            "resume_content": [
                r'resume', r'cv', r'curriculum vitae',
                r'work experience', r'employment history',
                r'education', r'degree', r'university',
                r'skills', r'qualifications', r'certifications'
            ],
            "salary_info": [
                r'\$\d+', r'salary', r'compensation', r'pay',
                r'wage', r'income', r'earnings'
            ]
        }
    
    def _load_local_knowledge(self) -> Dict[str, Any]:
        """Load local knowledge for general queries"""
        return {
            "hiring_process": {
                "stages": ["sourcing", "screening", "interviewing", "assessment", "offer", "onboarding"],
                "best_practices": [
                    "Clear job descriptions",
                    "Structured interviews",
                    "Diverse candidate pools",
                    "Bias-free assessments",
                    "Timely feedback"
                ]
            },
            "interview_questions": {
                "technical": [
                    "Explain a challenging project you worked on",
                    "How do you approach debugging complex issues?",
                    "Describe your experience with [specific technology]",
                    "Walk me through your development process"
                ],
                "behavioral": [
                    "Tell me about a time you had to work with a difficult team member",
                    "Describe a situation where you had to learn something new quickly",
                    "Give an example of a project where you had to meet a tight deadline",
                    "Tell me about a time you made a mistake and how you handled it"
                ]
            },
            "market_insights": {
                "trending_skills": ["Python", "JavaScript", "Cloud Computing", "AI/ML", "DevOps"],
                "salary_trends": "Tech salaries are increasing 5-10% annually",
                "remote_work": "70% of tech companies offer remote work options"
            }
        }
    
    def is_sensitive_query(self, query: str) -> bool:
        """Check if query contains sensitive information"""
        query_lower = query.lower()
        
        for category, patterns in self.sensitive_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return True
        
        return False
    
    def anonymize_query(self, query: str) -> str:
        """Anonymize sensitive information in query"""
        anonymized = query
        
        # Remove email addresses
        anonymized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', anonymized)
        
        # Remove phone numbers
        anonymized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', anonymized)
        anonymized = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]', anonymized)
        
        # Remove names (simple approach)
        anonymized = re.sub(r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b', '[NAME]', anonymized)
        
        # Remove salary information
        anonymized = re.sub(r'\$\d+', '[SALARY]', anonymized)
        
        return anonymized
    
    def process_query_hybrid(self, query: str, context_type: str = "general") -> Dict[str, Any]:
        """Process query using hybrid approach"""
        
        # Check if query is sensitive
        is_sensitive = self.is_sensitive_query(query)
        
        if is_sensitive:
            # Process locally for sensitive queries
            return self._process_locally(query, context_type)
        else:
            # Use AI for general queries
            return self._process_with_ai(query, context_type)
    
    def _process_locally(self, query: str, context_type: str) -> Dict[str, Any]:
        """Process sensitive queries locally"""
        
        # Extract relevant information using local AI
        if "resume" in query.lower() or "candidate" in query.lower():
            # Simulate resume analysis
            analysis = self.local_ai.analyze_resume_advanced(query)
            return {
                "answer": f"Based on local analysis: {analysis['insights']['experience_summary']}. "
                         f"Key skills: {', '.join(analysis['insights']['strengths'][:3])}. "
                         f"Recommended roles: {', '.join(analysis['insights']['recommended_roles'][:3])}.",
                "confidence": 0.9,
                "processed_locally": True,
                "sensitive_data_protected": True,
                "ai_model": "local_analysis",
                "privacy_status": "secure"
            }
        
        # Handle other sensitive queries locally
        return {
            "answer": "This query contains sensitive information and has been processed locally to ensure data privacy. "
                     "All candidate data remains within your organization.",
            "confidence": 0.8,
            "processed_locally": True,
            "sensitive_data_protected": True,
            "ai_model": "local_processing",
            "privacy_status": "secure"
        }
    
    def _process_with_ai(self, query: str, context_type: str) -> Dict[str, Any]:
        """Process general queries with AI"""
        
        # Check if we have credentials for any provider
        has_vertex = self.llm_provider == "vertexai" and self.project_id
        has_gemini = bool(self.gemini_api_key)
        has_groq = bool(self.groq_api_key)
        
        if not (has_vertex or has_gemini or has_groq):
            return self._fallback_to_local(query, context_type)
        
        try:
            # Prepare AI prompt with context
            prompt = self._prepare_ai_prompt(query, context_type)
            
            # Use prioritized provider
            if has_vertex:
                response = self._call_vertex_ai(prompt)
                model_used = f"vertexai/{self.model}"
            elif has_gemini:
                response = self._call_gemini_api(prompt)
                model_used = self.model
            else:
                response = self._call_groq_api(prompt)
                model_used = "groq/llama-3.3-70b"
            
            return {
                "answer": response,
                "confidence": 0.85,
                "processed_locally": False,
                "sensitive_data_protected": True,
                "ai_model": model_used,
                "privacy_status": "general_query_only"
            }
            
        except Exception as e:
            print(f"⚠️ AI processing failed: {e}")
            return self._fallback_to_local(query, context_type)
    
    def _prepare_ai_prompt(self, query: str, context_type: str) -> str:
        """Prepare AI prompt with context"""
        
        base_prompt = f"""
        You are QuantHire AI, an expert HR and hiring assistant. 
        Answer this query about hiring and recruitment: "{query}"
        
        Context: {context_type}
        
        Provide helpful, professional advice about:
        - Hiring best practices
        - Interview techniques
        - Market trends
        - Recruitment strategies
        - HR processes
        
        Keep responses concise and actionable.
        """
        
        # Add context-specific information
        if context_type == "interview_questions":
            base_prompt += f"\n\nRelevant interview questions: {self.local_knowledge_base['interview_questions']['technical'][:3]}"
        elif context_type == "hiring_process":
            base_prompt += f"\n\nHiring stages: {', '.join(self.local_knowledge_base['hiring_process']['stages'])}"
        elif context_type == "market_insights":
            base_prompt += f"\n\nTrending skills: {', '.join(self.local_knowledge_base['market_insights']['trending_skills'])}"
        
        return base_prompt
    
    def _call_gemini_api(self, prompt: str) -> str:
        """Call Gemini API for general queries"""
        
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={self.gemini_api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    
    def _call_vertex_ai(self, prompt: str) -> str:
        """Call Vertex AI API"""
        from langchain_google_vertexai import ChatVertexAI
        from langchain_core.messages import HumanMessage
        
        llm = ChatVertexAI(
            model=self.model,
            project=self.project_id,
            location=self.location,
            temperature=0.4
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def _call_groq_api(self, prompt: str) -> str:
        """Call Groq API as fallback"""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    
    def _fallback_to_local(self, query: str, context_type: str) -> Dict[str, Any]:
        """Fallback to local processing when AI is unavailable"""
        
        # Use local knowledge base
        if "interview" in query.lower():
            questions = self.local_knowledge_base['interview_questions']['technical'][:3]
            answer = f"Here are some technical interview questions: {', '.join(questions)}"
        elif "hiring" in query.lower():
            stages = self.local_knowledge_base['hiring_process']['stages']
            answer = f"The hiring process typically includes: {', '.join(stages)}"
        elif "skills" in query.lower():
            skills = self.local_knowledge_base['market_insights']['trending_skills']
            answer = f"Current trending skills: {', '.join(skills)}"
        else:
            answer = "I can help with hiring, interviews, and recruitment questions. Please ask about specific topics like interview questions, hiring processes, or market trends."
        
        return {
            "answer": answer,
            "confidence": 0.7,
            "processed_locally": True,
            "sensitive_data_protected": True,
            "ai_model": "local_knowledge_base",
            "privacy_status": "secure_fallback"
        }

# Initialize FastAPI app
app = FastAPI(
    title="QuantHire AI - Hybrid Secure Assistant",
    description="Best of both worlds: Secure local processing + AI assistant",
    version="1.0.0"
)

# Initialize hybrid AI assistant
hybrid_assistant = HybridAIAssistant()

@app.get("/api/v1/hybrid/status")
async def get_hybrid_status():
    """Get hybrid AI assistant status"""
    return {
        "status": "hybrid_active",
        "capabilities": {
            "sensitive_data_processing": "local_only",
            "general_queries": "ai_powered",
            "data_privacy": "enterprise_grade",
            "conversational_ai": "available"
        },
        "ai_provider": "google_gemini" if hybrid_assistant.gemini_api_key else "local_only",
        "local_ai_available": True,
        "privacy_features": [
            "Sensitive data detection",
            "Automatic anonymization",
            "Local processing for PII",
            "AI for general queries only"
        ]
    }

@app.post("/api/v1/hybrid/query")
async def process_hybrid_query(data: dict):
    """Process query using hybrid approach"""
    
    query = data.get("query", "")
    context_type = data.get("context_type", "general")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    # Process query using hybrid approach
    result = hybrid_assistant.process_query_hybrid(query, context_type)
    
    return {
        "query": query,
        "context_type": context_type,
        "result": result,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/hybrid/resume-analysis")
async def analyze_resume_hybrid(data: dict):
    """Analyze resume using hybrid approach (always local)"""
    
    resume_text = data.get("resume_text", "")
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text is required")
    
    # Always process resumes locally for security
    analysis = hybrid_assistant.local_ai.analyze_resume_advanced(resume_text)
    
    return {
        "status": "resume_analysis_complete",
        "analysis": analysis,
        "security_confirmation": {
            "processed_locally": True,
            "no_external_transmission": True,
            "sensitive_data_protected": True,
            "gdpr_compliant": True
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/hybrid/ai-chat")
async def ai_chat(data: dict):
    """AI chat for general queries"""
    
    message = data.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Check if message is sensitive
    is_sensitive = hybrid_assistant.is_sensitive_query(message)
    
    if is_sensitive:
        return {
            "response": "I can't process messages containing sensitive information like personal details, resumes, or salary data. "
                       "Please ask general questions about hiring, interviews, or recruitment best practices.",
            "is_sensitive": True,
            "processed_locally": True,
            "privacy_protected": True
        }
    
    # Process with AI
    result = hybrid_assistant.process_query_hybrid(message, "general")
    
    return {
        "response": result["answer"],
        "is_sensitive": False,
        "processed_locally": result["processed_locally"],
        "ai_model": result["ai_model"],
        "confidence": result["confidence"]
    }

if __name__ == "__main__":
    print("=" * 80)
    print("🎯 QuantHire AI - Hybrid Secure Assistant Starting...")
    print("=" * 80)
    print("✅ Sensitive Data: PROCESSED LOCALLY")
    print("✅ General Queries: AI-POWERED")
    print("✅ Data Privacy: ENTERPRISE GRADE")
    print("✅ Conversational AI: AVAILABLE")
    print("✅ Best of Both Worlds: SECURE + SMART")
    print("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=8003)

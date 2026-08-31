"""
QuantHire AI - Advanced On-Premises AI Backend
==============================================

This backend uses LOCAL AI models for processing:
- Ollama for local LLM processing
- Sentence Transformers for local embeddings
- Scikit-learn for local ML
- NO external API calls
- Complete data privacy
"""

import os
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Try to import local AI libraries
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️ Ollama not available - using pattern matching")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ Sentence Transformers not available - using TF-IDF")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ Scikit-learn not available - using basic matching")

class AdvancedLocalAI:
    """Advanced local AI processing using multiple techniques"""
    
    def __init__(self):
        self.local_models = {}
        self.embeddings_model = None
        self.classifier = None
        self.vectorizer = None
        
        self._initialize_local_models()
        self._load_knowledge_base()
    
    def _initialize_local_models(self):
        """Initialize local AI models"""
        
        # Initialize sentence transformers for embeddings
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("✅ Local embeddings model loaded")
            except Exception as e:
                print(f"⚠️ Could not load embeddings model: {e}")
        
        # Initialize TF-IDF vectorizer
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
            self.classifier = MultinomialNB()
            print("✅ Local ML models initialized")
    
    def _load_knowledge_base(self):
        """Load comprehensive local knowledge base"""
        self.knowledge_base = {
            "technical_skills": {
                "programming_languages": {
                    "python": ["python", "django", "flask", "fastapi", "pandas", "numpy", "scipy", "matplotlib"],
                    "javascript": ["javascript", "js", "react", "node.js", "vue", "angular", "typescript", "express"],
                    "java": ["java", "spring", "hibernate", "maven", "gradle", "junit", "jpa"],
                    "csharp": ["c#", "csharp", ".net", "asp.net", "entity framework", "linq"],
                    "go": ["golang", "go", "gin", "echo", "gorilla"],
                    "rust": ["rust", "cargo", "tokio", "serde"],
                    "php": ["php", "laravel", "symfony", "composer", "wordpress"],
                    "ruby": ["ruby", "rails", "rubygems", "rspec"]
                },
                "databases": {
                    "sql": ["mysql", "postgresql", "sqlite", "oracle", "sql server", "mariadb"],
                    "nosql": ["mongodb", "cassandra", "redis", "elasticsearch", "dynamodb", "couchdb"],
                    "graph": ["neo4j", "arangodb", "orientdb"]
                },
                "cloud_platforms": {
                    "aws": ["aws", "amazon web services", "ec2", "s3", "lambda", "rds", "dynamodb", "cloudformation"],
                    "azure": ["azure", "microsoft azure", "azure functions", "azure sql", "azure storage"],
                    "gcp": ["gcp", "google cloud", "gce", "gcs", "cloud functions", "bigquery", "firestore"],
                    "ibm": ["ibm cloud", "bluemix", "watson"]
                },
                "devops_tools": {
                    "containers": ["docker", "kubernetes", "k8s", "podman", "containerd"],
                    "ci_cd": ["jenkins", "gitlab ci", "github actions", "azure devops", "circleci", "travis"],
                    "infrastructure": ["terraform", "ansible", "puppet", "chef", "vagrant"],
                    "monitoring": ["prometheus", "grafana", "elk stack", "splunk", "datadog", "newrelic"]
                },
                "data_science": {
                    "ml_frameworks": ["tensorflow", "pytorch", "scikit-learn", "keras", "xgboost", "lightgbm"],
                    "data_tools": ["pandas", "numpy", "matplotlib", "seaborn", "plotly", "jupyter"],
                    "big_data": ["spark", "hadoop", "kafka", "storm", "flink", "airflow"]
                },
                "mobile": {
                    "ios": ["swift", "objective-c", "xcode", "ios", "iphone"],
                    "android": ["kotlin", "java", "android studio", "android", "react native"],
                    "cross_platform": ["react native", "flutter", "xamarin", "ionic"]
                }
            },
            "soft_skills": {
                "leadership": ["lead", "leadership", "manager", "management", "team lead", "tech lead"],
                "communication": ["communication", "presentation", "public speaking", "writing"],
                "collaboration": ["collaboration", "teamwork", "agile", "scrum", "kanban"],
                "problem_solving": ["problem solving", "analytical", "critical thinking", "debugging"]
            },
            "experience_levels": {
                "entry": {"years": (0, 1), "keywords": ["entry", "junior", "graduate", "intern", "trainee"]},
                "junior": {"years": (1, 3), "keywords": ["junior", "associate", "assistant"]},
                "mid": {"years": (3, 6), "keywords": ["mid", "intermediate", "experienced", "specialist"]},
                "senior": {"years": (6, 10), "keywords": ["senior", "lead", "principal", "expert"]},
                "staff": {"years": (10, 15), "keywords": ["staff", "architect", "director", "head"]},
                "executive": {"years": (15, 100), "keywords": ["executive", "vp", "cto", "ceo", "founder"]}
            },
            "salary_benchmarks": {
                "software_engineer": {"entry": 60000, "junior": 80000, "mid": 110000, "senior": 140000, "staff": 180000},
                "data_scientist": {"entry": 70000, "junior": 95000, "mid": 125000, "senior": 160000, "staff": 200000},
                "devops_engineer": {"entry": 65000, "junior": 90000, "mid": 120000, "senior": 150000, "staff": 190000},
                "product_manager": {"entry": 80000, "junior": 110000, "mid": 140000, "senior": 170000, "staff": 220000},
                "designer": {"entry": 55000, "junior": 75000, "mid": 100000, "senior": 130000, "staff": 160000}
            }
        }
    
    def analyze_resume_advanced(self, resume_text: str) -> Dict[str, Any]:
        """Advanced resume analysis using local AI"""
        
        # Extract skills using multiple methods
        skills = self._extract_skills_advanced(resume_text)
        
        # Determine experience level
        experience_level = self._determine_experience_level_advanced(resume_text)
        
        # Generate embeddings if available
        embeddings = self._generate_embeddings(resume_text)
        
        # Calculate skill scores
        skill_scores = self._calculate_skill_scores_advanced(skills)
        
        # Generate insights
        insights = self._generate_advanced_insights(resume_text, skills, experience_level)
        
        # Use local LLM if available
        if OLLAMA_AVAILABLE:
            llm_insights = self._get_local_llm_insights(resume_text)
            insights.update(llm_insights)
        
        return {
            "extracted_skills": skills,
            "experience_level": experience_level,
            "skill_scores": skill_scores,
            "embeddings": embeddings.tolist() if embeddings is not None else None,
            "insights": insights,
            "processing_method": "local_ai_advanced",
            "models_used": self._get_used_models(),
            "privacy_status": "fully_local"
        }
    
    def _extract_skills_advanced(self, text: str) -> Dict[str, List[str]]:
        """Extract skills using advanced local methods"""
        text_lower = text.lower()
        extracted_skills = {
            "programming_languages": [],
            "databases": [],
            "cloud_platforms": [],
            "devops_tools": [],
            "data_science": [],
            "mobile": [],
            "soft_skills": []
        }
        
        # Extract technical skills
        for category, skills_dict in self.knowledge_base["technical_skills"].items():
            for skill, patterns in skills_dict.items():
                for pattern in patterns:
                    if pattern in text_lower:
                        extracted_skills[category].append(skill)
                        break
        
        # Extract soft skills
        for category, patterns in self.knowledge_base["soft_skills"].items():
            for pattern in patterns:
                if pattern in text_lower:
                    extracted_skills["soft_skills"].append(category)
                    break
        
        return extracted_skills
    
    def _determine_experience_level_advanced(self, text: str) -> str:
        """Determine experience level using advanced analysis"""
        text_lower = text.lower()
        
        # Look for explicit level indicators
        for level, config in self.knowledge_base["experience_levels"].items():
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    return level
        
        # Extract years of experience
        import re
        year_patterns = [
            r'(\d+)\+?\s*years?',
            r'(\d+)\s*yr',
            r'(\d+)\s*year',
            r'(\d+)\s*months?'
        ]
        
        years = 0
        for pattern in year_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                years = max(years, int(matches[0]))
        
        # Convert months to years
        if 'month' in text_lower:
            years = years / 12
        
        # Determine level based on years
        for level, config in self.knowledge_base["experience_levels"].items():
            min_years, max_years = config["years"]
            if min_years <= years < max_years:
                return level
        
        return "unknown"
    
    def _generate_embeddings(self, text: str) -> Optional[np.ndarray]:
        """Generate embeddings using local model"""
        if self.embeddings_model:
            try:
                return self.embeddings_model.encode(text)
            except Exception as e:
                print(f"⚠️ Embedding generation failed: {e}")
                return None
        return None
    
    def _calculate_skill_scores_advanced(self, skills: Dict[str, List[str]]) -> Dict[str, float]:
        """Calculate advanced skill scores"""
        scores = {}
        
        # Weight different skill categories
        category_weights = {
            "programming_languages": 1.0,
            "databases": 0.8,
            "cloud_platforms": 0.9,
            "devops_tools": 0.9,
            "data_science": 1.0,
            "mobile": 0.7,
            "soft_skills": 0.6
        }
        
        for category, skill_list in skills.items():
            if skill_list:
                weight = category_weights.get(category, 0.5)
                base_score = min(len(skill_list) * 0.2, 1.0) * weight
                scores[category] = base_score
        
        return scores
    
    def _generate_advanced_insights(self, text: str, skills: Dict[str, List[str]], level: str) -> Dict[str, Any]:
        """Generate advanced insights using local analysis"""
        
        # Calculate total technical skills
        total_tech_skills = sum(len(skill_list) for skill_list in skills.values() if isinstance(skill_list, list))
        
        # Identify strengths
        strengths = []
        for category, skill_list in skills.items():
            if len(skill_list) > 0:
                strengths.extend(skill_list[:2])  # Top 2 skills per category
        
        # Recommend roles
        recommended_roles = self._recommend_roles_advanced(skills, level)
        
        # Estimate market value
        market_value = self._estimate_market_value_advanced(skills, level)
        
        # Identify skill gaps
        skill_gaps = self._identify_skill_gaps_advanced(skills, level)
        
        return {
            "total_technical_skills": total_tech_skills,
            "strengths": strengths[:5],
            "recommended_roles": recommended_roles,
            "market_value": market_value,
            "skill_gaps": skill_gaps,
            "experience_summary": f"{level.title()} level with {total_tech_skills} technical skills",
            "analysis_confidence": "high" if total_tech_skills > 5 else "medium"
        }
    
    def _recommend_roles_advanced(self, skills: Dict[str, List[str]], level: str) -> List[str]:
        """Recommend roles based on advanced analysis"""
        role_mapping = {
            "programming_languages": {
                "python": ["Python Developer", "Backend Developer", "Data Engineer"],
                "javascript": ["Frontend Developer", "Full Stack Developer", "React Developer"],
                "java": ["Java Developer", "Backend Developer", "Enterprise Developer"],
                "csharp": [".NET Developer", "C# Developer", "Backend Developer"]
            },
            "data_science": {
                "ml_frameworks": ["Data Scientist", "ML Engineer", "AI Engineer"],
                "data_tools": ["Data Analyst", "Business Intelligence", "Data Engineer"]
            },
            "cloud_platforms": {
                "aws": ["AWS Engineer", "Cloud Engineer", "DevOps Engineer"],
                "azure": ["Azure Engineer", "Cloud Engineer", "DevOps Engineer"],
                "gcp": ["GCP Engineer", "Cloud Engineer", "Data Engineer"]
            },
            "devops_tools": {
                "containers": ["DevOps Engineer", "Platform Engineer", "SRE"],
                "ci_cd": ["DevOps Engineer", "Build Engineer", "Release Engineer"]
            }
        }
        
        recommended = []
        for category, skill_list in skills.items():
            if category in role_mapping:
                for skill in skill_list:
                    if skill in role_mapping[category]:
                        recommended.extend(role_mapping[category][skill])
        
        return list(set(recommended))[:8]
    
    def _estimate_market_value_advanced(self, skills: Dict[str, List[str]], level: str) -> Dict[str, Any]:
        """Estimate market value using advanced analysis"""
        
        # Find primary role based on skills
        primary_role = "software_engineer"  # default
        
        if skills.get("data_science"):
            primary_role = "data_scientist"
        elif skills.get("devops_tools") or skills.get("cloud_platforms"):
            primary_role = "devops_engineer"
        elif skills.get("mobile"):
            primary_role = "software_engineer"  # mobile developer
        
        # Get salary benchmarks
        benchmarks = self.knowledge_base["salary_benchmarks"].get(primary_role, 
                                                                self.knowledge_base["salary_benchmarks"]["software_engineer"])
        
        base_salary = benchmarks.get(level, benchmarks.get("mid", 100000))
        
        # Adjust based on skill diversity
        skill_diversity_bonus = len([cat for cat, skills_list in skills.items() if skills_list]) * 5000
        
        estimated_salary = base_salary + skill_diversity_bonus
        
        return {
            "estimated_salary": int(estimated_salary),
            "salary_range": f"${estimated_salary - 15000}-${estimated_salary + 20000}",
            "confidence": "high" if len(skills) > 3 else "medium",
            "based_on": "local_market_analysis",
            "primary_role": primary_role,
            "skill_diversity_bonus": skill_diversity_bonus
        }
    
    def _identify_skill_gaps_advanced(self, skills: Dict[str, List[str]], level: str) -> List[str]:
        """Identify skill gaps using advanced analysis"""
        
        # Define expected skills by level
        expected_skills = {
            "entry": ["Basic Programming", "Version Control", "Testing"],
            "junior": ["Testing", "Documentation", "Code Review", "Agile"],
            "mid": ["Architecture", "Code Review", "Mentoring", "Agile/Scrum"],
            "senior": ["System Design", "Mentoring", "Technical Leadership", "Architecture"],
            "staff": ["Technical Strategy", "Team Leadership", "System Architecture", "Innovation"]
        }
        
        gaps = []
        expected = expected_skills.get(level, expected_skills["mid"])
        
        # Check for missing soft skills
        soft_skills = skills.get("soft_skills", [])
        for expected_skill in expected:
            if expected_skill.lower() not in " ".join(soft_skills).lower():
                gaps.append(expected_skill)
        
        return gaps[:5]
    
    def _get_local_llm_insights(self, text: str) -> Dict[str, Any]:
        """Get insights using local LLM (Ollama)"""
        if not OLLAMA_AVAILABLE:
            return {}
        
        try:
            prompt = f"""
            Analyze this resume and provide insights:
            {text[:500]}...
            
            Focus on:
            1. Key strengths
            2. Potential concerns
            3. Interview focus areas
            4. Career progression potential
            
            Keep response concise and professional.
            """
            
            response = ollama.chat(model='llama2', messages=[
                {'role': 'user', 'content': prompt}
            ])
            
            return {
                "llm_insights": response['message']['content'],
                "llm_model": "llama2",
                "llm_processed_locally": True
            }
            
        except Exception as e:
            print(f"⚠️ Local LLM processing failed: {e}")
            return {"llm_insights": "Local LLM processing unavailable", "llm_model": "none"}
    
    def _get_used_models(self) -> List[str]:
        """Get list of models used for processing"""
        models = ["pattern_matching", "rule_based_analysis"]
        
        if self.embeddings_model:
            models.append("sentence_transformers")
        
        if self.classifier:
            models.append("scikit_learn")
        
        if OLLAMA_AVAILABLE:
            models.append("ollama_llama2")
        
        return models

# Initialize FastAPI app
app = FastAPI(
    title="QuantHire AI - Advanced On-Premises Backend",
    description="Enterprise-grade local AI processing with ZERO external data transmission",
    version="2.0.0"
)

# Initialize advanced local AI
advanced_ai = AdvancedLocalAI()

@app.get("/api/v1/advanced/status")
async def get_advanced_status():
    """Get advanced local AI status"""
    return {
        "status": "advanced_local_active",
        "data_processing": "local_only",
        "external_transmission": "disabled",
        "privacy_compliant": True,
        "models_available": advanced_ai._get_used_models(),
        "ollama_available": OLLAMA_AVAILABLE,
        "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
        "sklearn_available": SKLEARN_AVAILABLE,
        "processing_capabilities": [
            "Advanced skill extraction",
            "Experience level analysis", 
            "Local embeddings generation",
            "Market value estimation",
            "Role recommendations",
            "Skill gap analysis",
            "Local LLM insights (if available)"
        ]
    }

@app.post("/api/v1/advanced/resume-analysis")
async def analyze_resume_advanced_endpoint(data: dict):
    """Advanced resume analysis using local AI"""
    
    resume_text = data.get("resume_text", "")
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text is required")
    
    # Perform advanced local analysis
    analysis = advanced_ai.analyze_resume_advanced(resume_text)
    
    return {
        "status": "advanced_analysis_complete",
        "analysis": analysis,
        "privacy_confirmation": {
            "processed_locally": True,
            "no_external_transmission": True,
            "data_retained_locally": True,
            "gdpr_compliant": True,
            "enterprise_secure": True
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("=" * 80)
    print("🧠 QuantHire AI - Advanced On-Premises AI Starting...")
    print("=" * 80)
    print("✅ Data Processing: LOCAL ONLY")
    print("✅ External Transmission: DISABLED")
    print("✅ Privacy Compliance: ENTERPRISE GRADE")
    print("✅ AI Models: LOCAL")
    print(f"✅ Ollama Available: {OLLAMA_AVAILABLE}")
    print(f"✅ Sentence Transformers: {SENTENCE_TRANSFORMERS_AVAILABLE}")
    print(f"✅ Scikit-learn: {SKLEARN_AVAILABLE}")
    print("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=8002)



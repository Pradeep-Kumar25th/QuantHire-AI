/** User-facing copy for Azure Non-Prod (AKS) — avoid Milvus/localhost dev references. */

export const AZURE_VECTOR_STORE_LABEL = "Azure Postgres pgvector";

export const AZURE_LLM_LABEL = "Azure OpenAI";

export const AZURE_BACKEND_HINT =
  "Ensure the API pod is ready (/readyz), BFF responds at /api/health, and Azure OpenAI + pgvector secrets are configured.";

export const AZURE_MATCHING_DATA_HINT =
  "Upload resumes (Candidates) and generate or save job descriptions first. Data is stored in Azure Postgres pgvector.";

export const AZURE_HSS_HINT =
  "HSS-D matching uses Azure OpenAI and pgvector. Ensure resumes and JDs exist in the vector store before launching the swarm.";

export const AZURE_JD_HINT =
  "Generate a job description, then save it so matching and QuantChat can use it.";

export const AZURE_QUANTCHAT_HINT =
  "QuantChat uses Azure OpenAI and pgvector RAG. Check API logs if chat requests return 500.";

export const AZURE_RESUME_HINT =
  "Resume parsing uses Azure Document Intelligence and Azure OpenAI, then stores embeddings in pgvector.";

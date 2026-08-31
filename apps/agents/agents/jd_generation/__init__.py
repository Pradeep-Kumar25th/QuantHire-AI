# JD Generation Package — enforce Vertex ADC before any agent/LLM imports.
try:
    from agents.llm.chat_factory import ensure_llm_env, llm_provider

    ensure_llm_env()
    if llm_provider() != "openai":
        from agents.gcp_vertex_credentials import bootstrap_vertex_adc

        bootstrap_vertex_adc(load_env=True, log_status=False)
except Exception:
    pass

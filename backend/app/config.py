from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    active_college: str = "SRKI"
    srki_dataset_a: Path = Path(r"E:\Final_SRKI_dataset\Dataset_A_SRKI.json")
    srki_dataset_b: Path = Path(r"E:\Final_SRKI_dataset\Dataset_B_SRKI.json")
    srki_json_data_dir: Path | None = Path(
        r"C:\Users\Shruti Revdiwala\COLLEGE_CHATBOT_RAG\data\json-data"
    )

    intent_model_dir: Path = ROOT / "models" / "srki_intent"
    rag_index_dir: Path = ROOT / "data" / "index" / "srki"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    intent_base_model: str = "distilbert-base-uncased"
    max_seq_length: int = 128

    host: str = "127.0.0.1"
    port: int = 8001

    web_scrape_enabled: bool = True
    web_seed_urls: str = (
        "https://www.srki.ac.in/,"
        "https://www.srki.ac.in/pages/admission-corner/,"
        "https://www.srki.ac.in/contact/,"
        "https://www.srki.ac.in/pages/srki-constituent-college-of-sarvajanik-university-/,"
        "https://www.srki.ac.in/pages/history/"
    )
    web_cache_dir: Path = ROOT / "data" / "web_cache"
    web_cache_ttl_hours: int = 24
    web_max_pages: int = 40
    web_request_timeout: int = 15
    web_request_delay_sec: float = 0.4
    web_live_on_query: bool = False
    web_user_agent: str = "SRKI-Hybrid-Assistant/1.0 (educational; +local)"

    def web_seed_urls_list(self) -> list[str]:
        return [u.strip() for u in self.web_seed_urls.split(",") if u.strip()]

    # --- Multi-intent + unseen-intent handling ---
    multi_intent_enabled: bool = True
    intent_confidence_threshold: float = 0.40
    multi_intent_max: int = 3

    # --- External web search (non-SRKI institutions / out-of-scope) ---
    external_search_enabled: bool = True
    external_search_max_results: int = 3
    external_search_fetch_pages: int = 0
    external_search_timeout: int = 8
    external_search_cache_ttl_hours: int = 12
    external_search_cache_dir: Path = ROOT / "data" / "search_cache"
    # Institutions explicitly treated as external (web-search routed)
    external_institutions: str = (
        "vnsgu,veer narmad,veer narmad south gujarat university,south gujarat university,"
        "gtu,gujarat technological university,gujarat university,svnit,nit surat,"
        "auro university,uka tarsadia,bhagwan mahavir university"
    )

    # --- Optional grounded generative model (FLAN-T5) ---
    use_generator: bool = False
    generator_model: str = "google/flan-t5-base"
    generator_max_input_chars: int = 3500
    generator_max_new_tokens: int = 220

    # --- General Education LLM brain (Groq) ---
    # assistant_mode: "auto" (use LLM brain when a key is set, else SRKI pipeline),
    # "education" (force LLM brain), or "srki" (force the local SRKI pipeline).
    assistant_mode: str = "auto"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 700
    llm_request_timeout: int = 25
    edu_history_turns: int = 4
    edu_search_max_queries: int = 2
    edu_fast_mode: bool = True
    edu_asset_harvest_pages: int = 3
    edu_pdf_max_read: int = 2
    edu_site_nav_max_pages: int = 14
    edu_site_nav_max_depth: int = 5
    edu_official_page_extracts: int = 2
    # Restrict answers to SRKI only (Phase 1). Other institutions get a polite scope reply.
    edu_focus_srki_only: bool = True
    # Show suggested question chips in the chat UI.
    ui_show_suggestions: bool = False

    # --- Conversation logging (live database) ---
    conversation_logging_enabled: bool = True
    db_path: Path = ROOT / "data" / "conversations.db"

    # --- Admin dashboard (protect /admin and conversation APIs) ---
    admin_username: str = "admin"
    admin_password: str = ""
    admin_token_ttl_hours: int = 24

    def external_institutions_list(self) -> list[str]:
        return [x.strip().lower() for x in self.external_institutions.split(",") if x.strip()]

    def use_education_mode(self) -> bool:
        if self.assistant_mode == "education":
            return True
        if self.assistant_mode == "srki":
            return False
        return bool(self.groq_api_key.strip())


settings = Settings()

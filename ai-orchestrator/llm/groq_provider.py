import structlog
from functools import lru_cache
from langchain_groq import ChatGroq
from llm.base import _ChatAdapter
from config import get_settings

logger = structlog.get_logger()


@lru_cache()
def create_llm() -> _ChatAdapter:
    settings = get_settings()
    logger.info("Initialising Groq LLM", model=settings.groq_model)
    model = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0.0,
    )
    return _ChatAdapter(model)

import structlog
from functools import lru_cache
from langchain_openai import ChatOpenAI
from llm.base import _ChatAdapter
from config import get_settings

logger = structlog.get_logger()


@lru_cache()
def create_llm() -> _ChatAdapter:
    settings = get_settings()
    logger.info("Initialising OpenAI LLM", model=settings.openai_model)
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=0.0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    return _ChatAdapter(model)

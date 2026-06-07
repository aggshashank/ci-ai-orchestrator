import structlog
from functools import lru_cache
from langchain_openai import AzureChatOpenAI
from llm.base import _ChatAdapter
from config import get_settings

logger = structlog.get_logger()


@lru_cache()
def create_llm() -> _ChatAdapter:
    settings = get_settings()
    logger.info("Initialising Azure OpenAI LLM",
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment)
    model = AzureChatOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        temperature=0.0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    return _ChatAdapter(model)

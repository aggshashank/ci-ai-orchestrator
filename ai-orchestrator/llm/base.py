from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimum interface every LLM provider must satisfy.

    invoke() accepts a raw string prompt and returns a raw string.
    Agents expect JSON — each provider must ensure JSON-mode output either via
    a model parameter (format="json", response_format) or prompt instructions.
    """

    def invoke(self, prompt: str, **kwargs: Any) -> str: ...


class _ChatAdapter:
    """Adapts a LangChain BaseChatModel to the LLMProvider protocol.

    BaseChatModel.invoke() returns AIMessage; agents expect plain str.
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        return self._model.invoke(prompt, **kwargs).content

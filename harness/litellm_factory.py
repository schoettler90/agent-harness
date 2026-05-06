from typing import Any, Literal

from dotenv import load_dotenv
from litellm import LiteLLM
from loguru import logger

# Drop unsupported params (e.g. reasoning_effort) for the target provider
# litellm.drop_params = True


load_dotenv()
Provider = Literal["openai", "gemini", "anthropic", "ollama", "deepseek", "auto"]


class LiteLLMFactory:
    """
    Factory that returns LiteLLM OpenAI-compatible clients.

    Use resolve_model() alongside the client
    to keep calls provider-agnostic.
    """

    @staticmethod
    def detect_provider(
        model: str,
    ) -> Literal["openai", "gemini", "anthropic", "ollama", "deepseek"]:
        """Infer the provider from the model name."""
        if model.startswith("claude"):
            return "anthropic"
        elif model.startswith("gemini"):
            return "gemini"
        elif model.startswith("deepseek/") or ("/" not in model and model.startswith("deepseek")):
            return "deepseek"
        elif model.startswith("ollama/") or (
            "/" not in model and model.startswith(("qwen", "llama", "mistral", "phi"))
        ):
            return "ollama"
        else:
            return "openai"

    @staticmethod
    def resolve_model(model: str, provider: Provider = "auto") -> str:
        """Return the model string with the LiteLLM provider prefix applied."""
        resolved_provider = (
            LiteLLMFactory.detect_provider(model) if provider == "auto" else provider
        )

        if resolved_provider == "gemini" and not model.startswith("gemini/"):
            return f"gemini/{model}"
        if resolved_provider == "ollama" and not model.startswith("ollama/"):
            return f"ollama/{model}"
        if resolved_provider == "deepseek" and not model.startswith("deepseek/"):
            return f"deepseek/{model}"
        return model

    @staticmethod
    def get_client(
        timeout: float = 90.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> LiteLLM:
        """Return a synchronous OpenAI-compatible LiteLLM client."""
        return LiteLLM(timeout=timeout, max_retries=max_retries, **kwargs)


def stream_main() -> None:
    model_name = "gemini-3-flash-preview"
    model = LiteLLMFactory.resolve_model(model_name)
    client = LiteLLMFactory.get_client()

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Explain the theory of relativity in simple terms.",
            }
        ],
        stream=True,
        reasoning_effort="minimal",
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()


def structured_output_main() -> None:
    from pydantic import BaseModel, Field

    class ResearchSummary(BaseModel):
        title: str = Field(description="Concise title for the summary")
        key_points: list[str] = Field(description="Main takeaways")
        conclusion: str = Field(description="Overall conclusion")

    model_name = "gemini-2.5-flash"
    model = LiteLLMFactory.resolve_model(model_name)
    client = LiteLLMFactory.get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Summarize the theory of relativity."}],
        response_format=ResearchSummary,
        reasoning_effort="minimal",
    )

    output = response.choices[0].message.content
    result = ResearchSummary.model_validate_json(output)
    logger.info(result)


if __name__ == "__main__":
    stream_main()
    logger.success("LiteLLM factory initialized successfully.")

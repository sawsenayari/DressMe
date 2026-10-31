"""Bounded tool-calling orchestration for a DressMe gap-report assistant."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Protocol

from .config import AgentConfig
from .gateway import GatewayCallError, OpenAICompatibleGateway
from .images import PreparedImage, prepare_images
from .prompts import PROMPT_VERSION, build_system_prompt, build_user_context, detect_request_language
from .report import GapReportSource
from .sources import LLMGapAnalysisSource, WardrobeInventorySource


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_gap_report",
        "description": (
            "Read the user's precomputed DressMe wardrobe gap report. "
            "This is read-only and returns the highest-ranked missing pieces."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "top_k": {
                    "type": "integer",
                    "description": "Number of leading gap recommendations to return (1 to 10).",
                    "minimum": 1,
                    "maximum": 10,
                }
            },
            "required": ["top_k"],
            "additionalProperties": False,
        },
    },
}

WARDROBE_SUMMARY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_wardrobe_summary",
        "description": "Return a privacy-minimized summary of the FashionCLIP inventory: counts by slot and tentative color-label counts. It does not calculate compatibility or gaps.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
}

RANK_WARDROBE_GAPS_TOOL = {
    "type": "function",
    "function": {
        "name": "rank_wardrobe_gaps",
        "description": "Return a completed LLM-judged compatibility analysis whose outfit counts and marginal gains were calculated by the deterministic Python outfit counter. The result contains gain bounds when pair judgments are uncertain; it is not a product catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top gap archetypes to return (1 to 8).",
                    "minimum": 1,
                    "maximum": 8,
                }
            },
            "required": ["limit"],
            "additionalProperties": False,
        },
    },
}


class ChatCompletionsClient(Protocol):
    @property
    def chat(self) -> Any: ...


@dataclass(frozen=True)
class AgentResult:
    answer: str
    recommendations: list[dict[str, Any]]
    model: str
    prompt_version: str = PROMPT_VERSION
    used_tool: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_metadata: dict[str, Any] | None = None
    reported_model_ids: list[str] | None = None
    usage: dict[str, int] | None = None
    image_count: int = 0


class AgentError(RuntimeError):
    """Raised when the model response cannot be processed safely."""

    def __init__(self, message: str, category: str = "agent") -> None:
        super().__init__(message)
        self.category = category


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _first_message(response: Any) -> Any:
    choices = _value(response, "choices")
    if not isinstance(choices, (list, tuple)) or not choices:
        raise AgentError("The model returned an empty response.")
    message = _value(choices[0], "message")
    if message is None:
        raise AgentError("The model returned a malformed response.")
    return message


class DressMeGapAgent:
    """An agent with exactly one read-only tool and one bounded tool round."""

    def __init__(
        self,
        client: ChatCompletionsClient,
        config: AgentConfig,
        report_source: GapReportSource | None = None,
        wardrobe_source: WardrobeInventorySource | None = None,
        gap_analysis_source: LLMGapAnalysisSource | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._report_source = report_source
        self._wardrobe_source = wardrobe_source
        self._gap_analysis_source = gap_analysis_source
        self._gateway = OpenAICompatibleGateway(client, config)

    def _available_tools(self) -> list[dict[str, Any]]:
        tools = []
        if self._gap_analysis_source is not None:
            tools.append(RANK_WARDROBE_GAPS_TOOL)
        elif self._report_source is not None:
            tools.append(TOOL_DEFINITION)
        if self._wardrobe_source is not None:
            tools.append(WARDROBE_SUMMARY_TOOL)
        return tools

    def run(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        images: Iterable[str | Path] | str | Path | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AgentResult:
        if not isinstance(user_message, str) or not user_message.strip():
            raise ValueError("Please enter a question about wardrobe gaps.")
        if len(user_message) > self._config.max_user_chars:
            raise ValueError(f"Question is too long (limit: {self._config.max_user_chars} characters).")
        history = conversation_history or []
        if len(history) > 8 or any(
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message.get("role") not in {"user", "assistant"}
            or not isinstance(message.get("content"), str)
            for message in history
        ):
            raise ValueError("Conversation history is malformed or exceeds the turn limit.")
        if sum(len(message["content"]) for message in history) > 12000:
            raise ValueError("Conversation history exceeds the context limit.")

        context_message = build_user_context(context)
        image_paths = [images] if isinstance(images, (str, Path)) else (images or [])
        prepared_images: list[PreparedImage] = prepare_images(image_paths)
        request_model = (
            self._config.vision_model or self._config.model
            if prepared_images
            else self._config.model
        )
        request_language = detect_request_language(user_message)
        request_content = user_message.strip()
        if context_message:
            request_content += "\n\n" + context_message
        if prepared_images:
            request_content: str | list[dict[str, Any]] = [
                {"type": "text", "text": request_content},
                *(image.message_part() for image in prepared_images),
            ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_prompt(request_language)},
            *history,
            {"role": "user", "content": request_content},
        ]
        tools = self._available_tools()
        first = self._complete(
            messages,
            model=request_model,
            tools=tools,
            tool_choice="auto",
        )
        assistant_message = _first_message(first)
        tool_calls = _value(assistant_message, "tool_calls") or []
        if not tool_calls:
            answer = _value(assistant_message, "content")
            if not isinstance(answer, str) or not answer.strip():
                raise AgentError("The model returned an empty answer.")
            return AgentResult(
                answer=self._limit_answer(answer.strip()),
                recommendations=[],
                model=request_model,
                reported_model_ids=self._reported_models(first),
                usage=self._aggregate_usage(first),
                image_count=len(prepared_images),
            )
        if len(tool_calls) != 1:
            raise AgentError("The model must request at most one registered DressMe tool call.")

        tool_call = tool_calls[0]
        function = _value(tool_call, "function")
        tool_name = _value(function, "name")
        allowed_names = {tool["function"]["name"] for tool in tools}
        if tool_name not in allowed_names:
            raise AgentError("The model requested an unavailable tool.")
        arguments = self._parse_tool_arguments(tool_name, _value(function, "arguments"))
        tool_call_id = _value(tool_call, "id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise AgentError("The model returned a malformed tool-call identifier.")
        tool_result = self._execute_tool(tool_name, arguments)
        result_json = json.dumps(tool_result, ensure_ascii=False, separators=(",", ":"))
        if len(result_json) > 12000:
            raise AgentError("The tool result is too large to send to the model.")
        assistant_tool_call = {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments),
            },
        }
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": _value(assistant_message, "content"),
                    "tool_calls": [assistant_tool_call],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": result_json,
                },
            ]
        )
        final = self._complete(messages, model=request_model)
        final_message = _first_message(final)
        answer = _value(final_message, "content")
        if not isinstance(answer, str) or not answer.strip():
            raise AgentError("The model returned an empty answer.")
        answer = answer.strip()

        return AgentResult(
            answer=self._limit_answer(answer),
            recommendations=tool_result.get("recommendations", []),
            model=request_model,
            used_tool=tool_name,
            tool_arguments=arguments,
            tool_metadata=tool_result.get("metadata") if isinstance(tool_result.get("metadata"), dict) else None,
            reported_model_ids=self._reported_models(first, final),
            usage=self._aggregate_usage(first, final),
            image_count=len(prepared_images),
        )

    @staticmethod
    def _reported_models(*responses: Any) -> list[str] | None:
        models = []
        for response in responses:
            model = _value(response, "model")
            if isinstance(model, str) and model and model not in models:
                models.append(model)
        return models or None

    @staticmethod
    def _aggregate_usage(*responses: Any) -> dict[str, int] | None:
        totals: dict[str, int] = {}
        for response in responses:
            usage = _value(response, "usage")
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
                value = _value(usage, key) if usage is not None else None
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value
        return totals or None

    def _limit_answer(self, answer: str) -> str:
        if len(answer) <= self._config.max_answer_chars:
            return answer
        prefix = answer[: self._config.max_answer_chars]
        sentence_end = max(prefix.rfind(mark) for mark in (".", "!", "?", "。", "！", "？"))
        if sentence_end >= self._config.max_answer_chars // 2:
            return prefix[: sentence_end + 1].rstrip()
        return prefix.rsplit(" ", 1)[0].rstrip() + "…"

    def _complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any:
        request_model = model or self._config.model
        try:
            return self._gateway.complete(messages, model=request_model, **kwargs)
        except GatewayCallError as exc:
            raise AgentError(str(exc), category=exc.category) from exc

    @staticmethod
    def _parse_tool_arguments(tool_name: str, raw: Any) -> dict[str, int]:
        try:
            arguments = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            raise AgentError("The model returned invalid tool arguments.") from exc
        if not isinstance(arguments, dict):
            raise AgentError("The model returned unsupported tool arguments.")
        if tool_name == "get_gap_report":
            if set(arguments) != {"top_k"}:
                raise AgentError("The model returned unsupported tool arguments.")
            value, field, minimum, maximum = arguments["top_k"], "top_k", 1, 10
        elif tool_name == "rank_wardrobe_gaps":
            if set(arguments) != {"limit"}:
                raise AgentError("The model returned unsupported tool arguments.")
            value, field, minimum, maximum = arguments["limit"], "limit", 1, 8
        elif tool_name == "get_wardrobe_summary":
            if arguments:
                raise AgentError("The wardrobe summary tool accepts no arguments.")
            return {}
        else:
            raise AgentError("The model requested an unavailable tool.")
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise AgentError(f"{field} must be an integer between {minimum} and {maximum}.")
        return {field: value}

    def _execute_tool(self, tool_name: str, arguments: dict[str, int]) -> dict[str, Any]:
        try:
            if tool_name == "get_gap_report":
                if self._report_source is None:
                    raise AgentError("No fallback gap report is configured.")
                return self._report_source.get_gap_report(arguments["top_k"])
            if tool_name == "rank_wardrobe_gaps" and self._gap_analysis_source is not None:
                try:
                    return self._gap_analysis_source.rank_wardrobe_gaps(arguments["limit"])
                except Exception:
                    # A precomputed report is a last resort only after the
                    # primary LLM-judged analysis source fails.
                    if self._report_source is None:
                        raise
                    fallback = self._report_source.get_gap_report(min(arguments["limit"], 10))
                    fallback["metadata"]["fallback"] = True
                    fallback["metadata"]["fallback_reason"] = "primary_llm_gap_analysis_unavailable"
                    return fallback
            if tool_name == "get_wardrobe_summary" and self._wardrobe_source is not None:
                return self._wardrobe_source.get_wardrobe_summary()
        except Exception as exc:
            # Tool internals can include local paths; don't echo details to the model.
            raise AgentError("The requested DressMe data tool failed safely.", category="tool_error") from exc
        raise AgentError("The model requested an unavailable tool.")


class AgentConversation:
    """Small in-memory CLI conversation; recent text turns only, never persisted."""

    def __init__(self, agent: DressMeGapAgent, max_turns: int = 4) -> None:
        if not 1 <= max_turns <= 8:
            raise ValueError("max_turns must be between 1 and 8.")
        self._agent = agent
        self._max_turns = max_turns
        self._history: list[dict[str, str]] = []

    def run(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        images: Iterable[str | Path] | str | Path | None = None,
    ) -> AgentResult:
        result = self._agent.run(
            user_message,
            context=context,
            images=images,
            conversation_history=list(self._history),
        )
        self._history.extend(
            [
                {"role": "user", "content": user_message.strip()},
                {"role": "assistant", "content": result.answer},
            ]
        )
        self._history = self._history[-2 * self._max_turns :]
        while sum(len(message["content"]) for message in self._history) > 12000:
            self._history = self._history[2:]
        return result

    def clear(self) -> None:
        """Forget all in-memory turns for this CLI session."""
        self._history.clear()

from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingObservation:
    def __init__(self, record: dict) -> None:
        self.record = record

    def update(self, **kwargs) -> None:
        self.record["updates"].append(kwargs)


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []
        self.observations: list[dict] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    def get_current_trace_id(self) -> str:
        return "trace-from-test"

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        record = {"config": kwargs, "updates": []}
        self.observations.append(record)
        yield RecordingObservation(record)


def test_agent_records_prompt_version_with_v4_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    result = agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Email student@example.com; explain traces",
        correlation_id="req-12345678",
    )

    span_update = client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Email [REDACTED_EMAIL]; explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is client.prompt

    retrieval, generation = client.observations
    assert retrieval["config"]["name"] == "retrieval"
    assert retrieval["config"]["as_type"] == "retriever"
    assert retrieval["config"]["input"]["query_preview"].startswith(
        "Email [REDACTED_EMAIL]"
    )
    assert retrieval["updates"] == [{"output": {"doc_count": 1}}]

    assert generation["config"]["name"] == "llm-generation"
    assert generation["config"]["as_type"] == "generation"
    assert generation["config"]["model"] == agent.model
    assert generation["config"]["prompt"] is client.prompt
    assert "student@example.com" not in generation["config"]["input"]["prompt_preview"]
    assert generation["updates"][0]["usage_details"] == {
        "input": result.tokens_in,
        "output": result.tokens_out,
    }
    assert generation["updates"][0]["prompt"] is client.prompt
    assert abs(
        sum(generation["updates"][0]["cost_details"].values()) - result.cost_usd
    ) < 1e-9
    assert "student@example.com" not in str(generation["updates"])
    assert result.trace_id == "trace-from-test"

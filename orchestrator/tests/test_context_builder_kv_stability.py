"""KV-cache prefix-stability tests for the context builder (Sprint 7, WS-2).

These pin the I-13 invariant in code: the LLM prompt body must be a pure
function of the *content* of ACTIVE messages, NOT of any metadata that
can flip between calls (status, source, timestamps).
"""

from __future__ import annotations

from synapse_common.models import ContextMessage, MessageStatus

from orchestrator.llm.context_builder import ContextBuilder


class TestKVCacheStability:
    def test_status_changes_do_not_change_active_prompt(self) -> None:
        """Adding SUPERSEDED messages must not change the prompt the LLM sees.

        Two ContextBuilder runs with the same set of ACTIVE messages but a
        different number of trailing SUPERSEDED messages must produce the
        same prompt bytes (because the SUPERSEDED messages are filtered
        out before serialization).
        """
        builder = ContextBuilder()
        active = [
            ContextMessage(source="agent_a", content={"x": 1}),
            ContextMessage(source="agent_b", content={"y": 2}),
        ]
        with_more_superseded = [
            *active,
            ContextMessage(
                source="agent_c",
                content={"z": 3},
                status=MessageStatus.SUPERSEDED,
            ),
        ]
        h1 = builder.kv_cache_prefix_hash(active)
        h2 = builder.kv_cache_prefix_hash(with_more_superseded)
        assert h1 == h2

    def test_message_body_is_canonical_json_only(self) -> None:
        """The LLM body must NOT include source or status prefixes.

        Earlier versions emitted ``[agent_a|active] {...}`` which made the
        bytes depend on status. Verify those prefixes are gone.
        """
        builder = ContextBuilder()
        msg = ContextMessage(source="agent_a", content={"a": 1, "b": 2})
        out = builder.build_ollama_messages([msg])
        body = out[1]["content"]
        assert body == '{"a":1,"b":2}', f"unexpected body: {body!r}"
        assert "agent_a" not in body, "source must not appear in LLM body"
        assert "active" not in body, "status must not appear in LLM body"

    def test_same_content_same_hash_regardless_of_message_object_identity(self) -> None:
        builder = ContextBuilder()
        a = [ContextMessage(source="agent_a", content={"v": 1})]
        b = [ContextMessage(source="agent_a", content={"v": 1})]
        assert builder.kv_cache_prefix_hash(a) == builder.kv_cache_prefix_hash(b)

    def test_explicit_include_all_statuses_brings_back_superseded(self) -> None:
        builder = ContextBuilder()
        msgs = [
            ContextMessage(source="agent_a", content={"v": 1}),
            ContextMessage(
                source="agent_b",
                content={"v": 2},
                status=MessageStatus.SUPERSEDED,
            ),
        ]
        h_default = builder.kv_cache_prefix_hash(msgs)
        h_all = builder.kv_cache_prefix_hash(
            msgs,
            include_statuses=[
                MessageStatus.ACTIVE,
                MessageStatus.SUPERSEDED,
                MessageStatus.REJECTED,
                MessageStatus.ERROR,
            ],
        )
        assert h_default != h_all, (
            "Including SUPERSEDED messages must change the prompt hash; "
            "if these are equal the filter is broken."
        )

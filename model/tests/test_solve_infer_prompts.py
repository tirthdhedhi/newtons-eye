import json

import httpx
import pytest

from parser_model import paths
from parser_model.infer import ChatClient, InferConfig, clean_output
from parser_model.prompts import build_messages, build_system_prompt, pick_few_shots
from parser_model.solve import parse_output

SCHEMA = {"type": "object"}
MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]


def ok_body(text='{"a": 1}'):
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 3}}


def client(handler, **cfg):
    config = InferConfig(base_url="http://srv/v1", model="m", **cfg)
    return ChatClient(config, SCHEMA, transport=httpx.MockTransport(handler))


# --- solve.parse_output ---


def test_parse_output_ok_with_warnings():
    r = parse_output(0, '{"a": 1.5}', "warning: x: no shape\nwarning: y: no duration\n")
    assert r.ok and r.answers == {"a": 1.5}
    assert r.warnings == ["x: no shape", "y: no duration"]


def test_parse_output_validation_failure():
    r = parse_output(1, "", json.dumps({"issues": [{"path": "bodies", "message": "required"}]}))
    assert not r.ok and r.issues[0]["path"] == "bodies" and r.answers is None


def test_parse_output_query_failure_keeps_answers():
    r = parse_output(2, '{"a": null}', "error: a: no stop\n")
    assert r.exit_code == 2 and r.answers == {"a": None} and r.errors == ["a: no stop"]


# --- prompts ---


def test_few_shots_never_include_the_scored_example():
    for ex in ("floor-push", "projectile", "atwood", "table-hanging"):
        shots = pick_few_shots(ex)
        assert len(shots) == 3 and ex not in shots


def test_few_shots_are_deterministic_and_authoring_only():
    assert pick_few_shots("floor-push") == pick_few_shots("floor-push")
    for ex in pick_few_shots(None, k=10):
        assert paths.authoring_path(ex).exists()


def test_system_prompt_has_schema_and_excludes_own_example():
    own = json.loads(paths.authoring_path("projectile").read_text())["title"]
    prompt = build_system_prompt("projectile")
    assert "JSON only" not in prompt and "ONE JSON object" in prompt
    assert '"$schema"' in prompt
    assert own not in prompt
    assert prompt.count("Problem:") == 3
    assert '"$schema"' not in build_system_prompt("projectile", include_schema=False)


def test_build_messages_shape():
    msgs = build_messages("A 5 kg block.", "floor-push")
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "A 5 kg block." in msgs[1]["content"]


# --- infer ---


def test_clean_output():
    assert clean_output('<think>x</think> {"a": 1}') == '{"a": 1}'
    assert clean_output('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert clean_output("thinking...</think>{}") == "{}"


def test_plain_request_and_no_think():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=ok_body())

    c = client(handler, no_think=True)
    out = c.complete(MSGS)
    assert out.text == '{"a": 1}' and out.mode == "free"
    body = seen[0]
    assert body["temperature"] == 0.0
    assert body["messages"][-1]["content"].endswith("/no_think")
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "response_format" not in body
    assert MSGS[-1]["content"] == "q"  # input not mutated


def test_no_think_params_are_dropped_when_the_server_rejects_them():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if "chat_template_kwargs" in body:
            return httpx.Response(400, text="unknown field chat_template_kwargs")
        return httpx.Response(200, json=ok_body())

    c = client(handler, no_think=True)
    assert c.complete(MSGS).text == '{"a": 1}'
    c.complete(MSGS)
    assert len(seen) == 3  # rejected, retried, then remembered
    assert "chat_template_kwargs" not in seen[-1]


def test_constrained_uses_json_schema_first():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=ok_body())

    out = client(handler, constrained=True).complete(MSGS)
    assert out.mode == "json_schema"
    assert seen[0]["response_format"]["type"] == "json_schema"
    assert seen[0]["response_format"]["json_schema"]["schema"] == SCHEMA


def test_constrained_falls_back_through_native_options():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(
            (
                request.url.path,
                sorted(set(body) & {"response_format", "guided_json", "json_schema", "format"}),
            )
        )
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": '{"a": 2}'}, "eval_count": 5})
        return httpx.Response(400, text="unsupported")

    c = client(handler, constrained=True)
    out = c.complete(MSGS)
    assert out.mode == "ollama_native" and out.text == '{"a": 2}'
    assert [p for p, _ in calls] == ["/v1/chat/completions"] * 3 + ["/api/chat"]
    assert calls[1][1] == ["guided_json"] and calls[2][1] == ["json_schema"]
    assert calls[3][1] == ["format"]
    c.complete(MSGS)  # the working mode is remembered
    assert [p for p, _ in calls[4:]] == ["/api/chat"]


def test_llama_cpp_mode_is_found_when_vllm_option_is_rejected():
    def handler(request):
        body = json.loads(request.content)
        if "json_schema" in body and "response_format" not in body:
            return httpx.Response(200, json=ok_body())
        return httpx.Response(422, text="bad")

    assert client(handler, constrained=True).complete(MSGS).mode == "llama_cpp"


def test_server_errors_are_not_swallowed():
    from parser_model.infer import InferError

    c = client(lambda r: httpx.Response(500, text="boom"), constrained=True)
    with pytest.raises(InferError, match="500"):
        c.complete(MSGS)

"""VLLMBackend against a fake transport and a fake tokenizer: payload shape (canonical token ids, seed, sampling,
stop ids) and the exact-readout path (pipeline lineup.readout)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mp.backend import VLLMBackend  # noqa: E402


class Tok:
    eos_token_id = 1
    bos_token = "<bos>"

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in text]} if len(text) > 1 else {"input_ids": [100 + ord(text)]}

    def convert_tokens_to_ids(self, t):
        return 7

    def encode(self, text, add_special_tokens=False):
        return [ord(c) % 50 + 2 for c in text]


class Transport:
    def __init__(self):
        self.payloads = []

    def __call__(self, p):
        self.payloads.append(p)
        if p["max_tokens"] == 1:
            top = {f"token_id:{100 + ord('A')}": -0.2, f"token_id:{100 + ord('B')}": -1.8, "token_id:9": -6.0}
            return {"choices": [{"logprobs": {"top_logprobs": [top], "tokens": [f"token_id:{100 + ord('A')}"],
                                              "token_logprobs": [-0.2]}}]}
        return {"choices": [{"text": "A", "finish_reason": "stop"}]}


def test_vllm_payload_and_readout(monkeypatch):
    tr = Transport()
    be = VLLMBackend("gemma-2-9b-it", Tok(), transport=tr)
    monkeypatch.setattr(be.ser, "apply_to_tokenizer", lambda tok, msgs, add_generation_prompt=True: [5, 6, 7])
    msgs = [{"role": "user", "content": "Q?"}]
    out = be.generate(msgs, seed=2 ** 40 + 3, max_tokens=4, temperature=0.6, top_p=0.9)
    p = tr.payloads[-1]
    assert out["text"] == "A" and p["prompt"] == [5, 6, 7] and p["temperature"] == 0.6 and p["top_p"] == 0.9
    assert 0 <= p["seed"] < 2 ** 31 and p["stop_token_ids"] == [1, 7]
    ro = be.readout(msgs)
    assert abs(ro["p"]["A"] + ro["p"]["B"] + ro["non_option_mass"] - 1) < 1e-9 and ro["p"]["A"] > ro["p"]["B"]

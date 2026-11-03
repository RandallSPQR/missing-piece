"""Model backends. A backend serializes with the PINNED pipeline's canonical serializer for the model's family
(model_io.get(family).serialize_messages; the server's chat template is never used), generates with an explicit seed,
and reads exact option probabilities with lineup.readout.

  MockBackend   CPU only: deterministic text and probabilities from a hash of (serialized prompt, seed). Used for the
                harness, the branch-isolation check (S4 CPU half) and analysis validation. Never a source of findings.
  VLLMBackend   the lineup vLLM server (pipeline v1.2.0 serving stack, started by the pipeline's own console scripts on
                an approved pod). Prompt = canonical token ids; /v1/completions; batch size 1; seeded sampling.
"""
from __future__ import annotations

import hashlib
import math
import random


def serializer_for(model: str):
    import sae_ethos_pipeline  # noqa: F401
    import lineup
    import model_io
    return model_io.get(lineup.models()[model]["family"])


class _Base:
    def __init__(self, model: str):
        self.model = model
        self.ser = serializer_for(model)

    def serialize(self, messages) -> str:
        return self.ser.serialize_messages(messages, add_generation_prompt=True)

    def prompt_sha256(self, messages) -> str:
        return hashlib.sha256(self.serialize(messages).encode()).hexdigest()


class MockBackend(_Base):
    WORDS = ("the report record shows answer group agree think evidence vote round we should consider check said "
             "registry source told reliable option detail before after clear").split()

    def __init__(self, model: str = "gemma-2-9b-it", length=(50, 130)):
        super().__init__(model)
        self.length = length
        self.n_calls = 0

    def _rng(self, messages, seed):
        h = hashlib.sha256((self.serialize(messages) + f"|{seed}").encode()).hexdigest()
        return random.Random(int(h[:16], 16))

    def generate(self, messages, seed, max_tokens, temperature, top_p) -> dict:
        self.n_calls += 1
        rng = self._rng(messages, seed)
        if max_tokens <= 8:                                   # a vote
            return {"text": rng.choice(["A", "B", "A", "B", "A.", "Maybe"] if rng.random() < 0.02 else ["A", "B"]),
                    "finish_reason": "stop"}
        n = rng.randint(*self.length) if max_tokens > 150 else rng.randint(10, 30)
        return {"text": " ".join(rng.choice(self.WORDS) for _ in range(n)), "finish_reason": "stop"}

    def readout(self, messages) -> dict:
        self.n_calls += 1
        rng = self._rng(messages, "readout")
        x = rng.gauss(0, 1.5)
        non = rng.random() * 0.003
        pa = (1 - non) / (1 + math.exp(-x))
        return {"p": {"A": pa, "B": 1 - non - pa}, "non_option_mass": non, "logit_AB": x}


class VLLMBackend(_Base):
    """Needs a running lineup server and the model's tokenizer (identity-checked by the pipeline's fetch script)."""

    def __init__(self, model: str, tokenizer, base_url="http://localhost:8000/v1", served_name=None, transport=None):
        super().__init__(model)
        import sae_ethos_pipeline  # noqa: F401
        from lineup import readout as R
        self.R = R
        self.tok = tokenizer
        self.transport = transport or R.HTTPTransport(base_url)
        self.served = served_name or model
        self.option_ids = R.option_token_ids(tokenizer, ("A", "B"))
        self.stop_ids = sorted({int(tokenizer.convert_tokens_to_ids(self.ser.END_OF_TURN)), int(tokenizer.eos_token_id)})

    def ids(self, messages):
        return self.ser.apply_to_tokenizer(self.tok, messages, add_generation_prompt=True)

    def generate(self, messages, seed, max_tokens, temperature, top_p) -> dict:
        payload = {"model": self.served, "prompt": list(self.ids(messages)), "max_tokens": int(max_tokens),
                   "temperature": float(temperature), "top_p": float(top_p), "seed": int(seed) % (2 ** 31),
                   "stop_token_ids": self.stop_ids, "skip_special_tokens": True}
        r = self.transport(payload)
        ch = r["choices"][0]
        return {"text": ch["text"], "finish_reason": ch.get("finish_reason")}

    def readout(self, messages) -> dict:
        return self.R.readout(self.transport, self.served, self.ids(messages), self.option_ids)

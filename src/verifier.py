"""
Verifier: Mistral-7B-Instruct-v0.3

Prompt V4 changes vs V2:
- Added numerical precision rule: fabricated % must appear exactly in evidence
- Added citation format rule: bibliographic claims require explicit citation match
"""

import re
import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
VALID_VERDICTS = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}
MAX_NEW_TOKENS = 80


PROMPT_TEMPLATE = """[INST] You are a fact-checking assistant. Given a CLAIM and supporting EVIDENCE, decide whether the evidence supports the claim.

CLAIM: {claim}

EVIDENCE:
{evidence_block}

Choose ONE verdict:

- SUPPORTED: The evidence directly confirms the claim, either explicitly or via clear semantic equivalence.

- CONTRADICTED: The evidence and the claim are about the same topic, but the evidence shows a result that disagrees with the claim. This includes cases where the evidence states "no significant difference" or "no effect" while the claim asserts an effect, or where evidence numbers/conclusions clearly oppose the claim.

- UNSUPPORTED: The evidence does not contain information about the specific subject matter of the claim. Use this only when evidence is off-topic or silent on the claim's specific assertion.

Special rules (apply these first):
1. If the CLAIM contains a specific percentage or number (e.g. "23%", "42%", "18% higher"), choose UNSUPPORTED unless that exact number appears in the evidence.
2. If the CLAIM is a bibliographic citation (contains author names + year + journal, e.g. "Smith et al., 2020, Journal of X"), choose UNSUPPORTED unless the evidence explicitly mentions that exact citation.

Decision rule: If the evidence discusses the same topic as the claim but disagrees with it, choose CONTRADICTED, not UNSUPPORTED.

You MUST respond in this EXACT format with no extra text:
Verdict: <SUPPORTED|UNSUPPORTED|CONTRADICTED>
Reasoning: <one short sentence>
[/INST]"""


def _format_evidence(evidence_list: list[str]) -> str:
    if not evidence_list:
        return "(no evidence retrieved)"
    return "\n".join(f"[{i+1}] {e}" for i, e in enumerate(evidence_list))


def _parse_verdict(model_output: str) -> dict:
    verdict = None
    verdict_match = re.search(r"Verdict\s*:\s*([A-Z_]+)", model_output, re.IGNORECASE)
    if verdict_match:
        candidate = verdict_match.group(1).upper().strip()
        if candidate in VALID_VERDICTS:
            verdict = candidate
    if verdict is None:
        for v in VALID_VERDICTS:
            if v in model_output.upper():
                verdict = v
                break
    if verdict is None:
        verdict = "UNSUPPORTED"

    reasoning = ""
    reasoning_match = re.search(r"Reasoning\s*:\s*(.+?)(?:\n|$)", model_output, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
        reasoning = re.sub(r"\s+", " ", reasoning)[:300]
    if not reasoning:
        reasoning = "(no reasoning extracted)"

    return {"verdict": verdict, "reasoning": reasoning}


class MistralVerifier:
    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id
        self.tokenizer = None
        self.model = None

    def _ensure_loaded(self):
        if self.model is not None:
            return
        print(f"[Verifier] Loading {self.model_id} (fp16)...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id, torch_dtype=torch.float16, device_map="auto",
        )
        gpu_mem = torch.cuda.memory_allocated() / 1e9
        print(f"[Verifier] Model loaded. GPU memory: {gpu_mem:.2f} GB")

    def verify(self, claim: str, evidence: list[str]) -> dict:
        self._ensure_loaded()
        prompt = PROMPT_TEMPLATE.format(claim=claim, evidence_block=_format_evidence(evidence))
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        full_text = self.tokenizer.decode(output[0], skip_special_tokens=True)
        prompt_text = self.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)
        reply = full_text[len(prompt_text):]
        return _parse_verdict(reply)

    def cleanup(self):
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            gc.collect()
            torch.cuda.empty_cache()


_verifier: MistralVerifier | None = None


def verify(claim: str, evidence: list[str]) -> dict:
    global _verifier
    if _verifier is None:
        _verifier = MistralVerifier()
    return _verifier.verify(claim, evidence)


def cleanup():
    global _verifier
    if _verifier is not None:
        _verifier.cleanup()
        _verifier = None

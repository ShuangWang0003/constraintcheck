"""
Step 5.1: Verify Mistral-7B-Instruct-v0.3 loads on RTX 4090 and produces
expected verdict-style output.

This is a one-off validation script — not part of the unit test suite.
Run once on Day 5 morning to confirm the GPU + model + format are aligned.
"""

import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"


def main():
    print(f"Step 5.1: Mistral load + inference sanity check")
    print(f"=" * 70)
    print(f"Model: {MODEL_ID}")
    print(f"GPU available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory total: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")
    print()

    # ---- Load tokenizer + model ------------------------------------------
    print("[1/3] Loading tokenizer...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    print(f"      Tokenizer loaded in {time.time() - t0:.1f}s")

    print("[2/3] Loading model (fp16 on GPU)...")
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    load_time = time.time() - t0
    print(f"      Model loaded in {load_time:.1f}s")
    print(f"      GPU memory after load: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # ---- Sanity check 1: trivial format compliance -----------------------
    print()
    print("[3/3] Running 3 sanity prompts...")
    print("-" * 70)

    prompts = [
        # Trivial format compliance test
        ("trivial", "[INST] Reply with exactly: Verdict: SUPPORTED [/INST]"),

        # Realistic verifier scenario: SUPPORTED case
        ("supported", """[INST] You are a fact-checking assistant. Decide if the EVIDENCE supports the CLAIM.

CLAIM: Aspirin reduces heart attack risk in patients with cardiovascular disease.

EVIDENCE:
A 2018 meta-analysis of 13 randomized controlled trials concluded that low-dose aspirin reduces the risk of myocardial infarction by 22% in adults with established cardiovascular disease.

Respond ONLY in this format:
Verdict: <SUPPORTED|UNSUPPORTED|CONTRADICTED>
Reasoning: <one sentence>
[/INST]"""),

        # Realistic verifier scenario: UNSUPPORTED case
        ("unsupported", """[INST] You are a fact-checking assistant. Decide if the EVIDENCE supports the CLAIM.

CLAIM: This finding was first reported by researchers at MIT in 2019.

EVIDENCE:
A 2018 meta-analysis of 13 randomized controlled trials concluded that low-dose aspirin reduces the risk of myocardial infarction by 22% in adults with established cardiovascular disease.

Respond ONLY in this format:
Verdict: <SUPPORTED|UNSUPPORTED|CONTRADICTED>
Reasoning: <one sentence>
[/INST]"""),
    ]

    for label, prompt in prompts:
        print(f"\n[{label}]")
        t0 = time.time()
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=80,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_time = time.time() - t0

        # Decode only the new tokens
        full_text = tokenizer.decode(output[0], skip_special_tokens=True)
        # Strip the prompt to show only model's reply
        reply = full_text[len(tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)):]

        print(f"  Generation time: {gen_time:.2f}s")
        print(f"  Reply: {reply.strip()}")

    print()
    print("=" * 70)
    print(f"Total GPU memory after all calls: {torch.cuda.memory_allocated()/1e9:.2f} GB")
    print("Sanity check complete.")


if __name__ == "__main__":
    main()

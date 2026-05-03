"""Quick look at PubMedQA structure before we build the eval set."""

from datasets import load_dataset

print("Loading PubMedQA pqa_labeled (from cache)...")
ds = load_dataset("pubmed_qa", "pqa_labeled")
print(f"Total examples: {len(ds['train'])}")
print()

print("=" * 70)
print("Example 0:")
print("=" * 70)
ex = ds['train'][0]
print(f"Top-level keys: {list(ex.keys())}")
print()
print(f"QUESTION:\n  {ex['question']}")
print()
print(f"CONTEXT type: {type(ex['context']).__name__}")
print(f"CONTEXT keys: {list(ex['context'].keys())}")
print(f"Number of context passages: {len(ex['context']['contexts'])}")
print()
print("First context passage (first 250 chars):")
print(f"  {ex['context']['contexts'][0][:250]}...")
print()
print(f"LONG ANSWER (full):")
print(f"  {ex['long_answer']}")
print()
print(f"FINAL DECISION: {ex['final_decision']}")
print()
print("=" * 70)
print("Distribution of final_decision across 1000 examples:")
print("=" * 70)
from collections import Counter
decisions = Counter(ex['final_decision'] for ex in ds['train'])
for k, v in decisions.most_common():
    print(f"  {k}: {v}")
print()
print("=" * 70)
print("Long-answer length stats (in words):")
print("=" * 70)
lengths = [len(ex['long_answer'].split()) for ex in ds['train']]
print(f"  min:    {min(lengths)} words")
print(f"  median: {sorted(lengths)[len(lengths)//2]} words")
print(f"  mean:   {sum(lengths) / len(lengths):.1f} words")
print(f"  max:    {max(lengths)} words")

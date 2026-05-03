"""Check how many long_answers contain extractable numbers."""

import re
from datasets import load_dataset

ds = load_dataset("pubmed_qa", "pqa_labeled")

n_total = len(ds['train'])
n_with_number = 0
n_with_percent = 0
samples_with_numbers = []

# Match integers, decimals, percentages
number_pattern = re.compile(r'\d+(?:\.\d+)?')
percent_pattern = re.compile(r'\d+(?:\.\d+)?\s*%')

for ex in ds['train']:
    answer = ex['long_answer']
    if number_pattern.search(answer):
        n_with_number += 1
        if len(samples_with_numbers) < 3:
            samples_with_numbers.append(answer)
    if percent_pattern.search(answer):
        n_with_percent += 1

print(f"Total long_answers: {n_total}")
print(f"Contain at least one number: {n_with_number} ({n_with_number/n_total*100:.1f}%)")
print(f"Contain at least one percentage: {n_with_percent} ({n_with_percent/n_total*100:.1f}%)")
print()
print("=" * 70)
print("3 example long_answers with numbers:")
print("=" * 70)
for i, s in enumerate(samples_with_numbers, 1):
    print(f"\n[{i}] {s[:300]}...")

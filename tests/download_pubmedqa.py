"""
Step 2.0a: Download PubMedQA to local HuggingFace cache.

This script just downloads the dataset (about 50MB) so subsequent steps
can load it from cache without network access.

Cache location: ~/.cache/huggingface/datasets/
"""

from datasets import load_dataset
import os

print("Downloading PubMedQA (pqa_labeled split, ~50MB)...")
print("Cache location: ~/.cache/huggingface/datasets/")
print()

ds = load_dataset("pubmed_qa", "pqa_labeled")

print("Download complete.")
print(f"Total examples in 'train' split: {len(ds['train'])}")
print()
print(f"Available splits: {list(ds.keys())}")
print()
print("Cache size:")
cache_dir = os.path.expanduser("~/.cache/huggingface/datasets")
os.system(f"du -sh {cache_dir} 2>/dev/null || echo 'cache dir not found yet'")

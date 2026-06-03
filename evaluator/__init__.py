"""LLM-as-judge evaluator for the Rubrics QA pipeline.

Mirrors what Zaidul's QA team does manually in columns N+ of the I/O sheet:
reads transcript + bot RCA output, decides Correct / Incorrect / Borderline
per (case, framework). Inner loop for prompt iteration; not a replacement
for human review.
"""

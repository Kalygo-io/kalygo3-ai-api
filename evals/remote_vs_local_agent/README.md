# AI School Agent Evaluations

This directory contains evaluation scripts for the AI School Agent.

## Q&A Evaluation

The Q&A evaluation script (`qa_eval.py`) evaluates the AI School Agent using a CSV dataset with questions and ground truth answers, using LLM-as-a-Judge for evaluation.

### Usage

```bash
# Run evaluation with a CSV file (AI School KB format)
uv run eval-ai-school-agent --csv evals/ai_school_agent/data/ai_school_kb_qa_dataset.csv

# Specify a custom dataset name
uv run eval-ai-school-agent --csv evals/ai_school_agent/data/ai_school_kb_qa_dataset.csv --dataset-name my-eval-dataset

# Use an existing LangSmith dataset (skip CSV loading)
uv run eval-ai-school-agent --use-existing-dataset --dataset-name my-eval-dataset

# Use existing dataset with environment variable
ENVIRONMENT=test uv run eval-ai-school-agent --use-existing-dataset --dataset-name ai-school-agent-qa-20251128-205205
```

### CSV Format

The script supports two CSV formats:

#### 1. AI School KB Format (Default)

- `q` (required): The question to ask the AI School Agent
- `a` (required): The expected/correct answer (ground truth)
- `created_at` (optional): Timestamp when the question was created
- `last_edited_at` (optional): Timestamp when the question was last edited

Example:

```csv
q,a,created_at,last_edited_at
"When did Phase 2 take place?","10/9/2025 to 11/3/2025",11/6/2025,11/6/2025
"How many participants were in AI School Phase 2?","26 participants",11/6/2025,11/6/2025
```

#### 2. Standard Format

- `question` (required): The question to ask the AI School Agent
- `ground_truth` (required): The expected/correct answer
- `category` (optional): Category for grouping (e.g., "programming", "math")
- `difficulty` (optional): Difficulty level (e.g., "easy", "medium", "hard")
- `metadata` (optional): JSON string with additional metadata

Example:

```csv
question,ground_truth,category,difficulty,metadata
"What is Python?","Python is a high-level programming language.","programming","easy","{}"
```

### Requirements

- `LANGSMITH_API_KEY`: Required for logging results to LangSmith
- `OPENAI_API_KEY`: Required for LLM-as-a-Judge evaluation
- Database access: The script will create a test account (`eval@test.com`) if needed
- Stripe: Optional (the script will proceed without Stripe customer creation if it fails)

### Evaluation Criteria

The LLM-as-a-Judge evaluator assesses answers based on:

1. **Accuracy**: Does it correctly answer the question?
2. **Completeness**: Does it cover all important aspects?
3. **Relevance**: Is the information relevant to the question?
4. **Clarity**: Is the answer clear and well-structured?
5. **Grounding**: Does it cite sources and avoid hallucination?

Each criterion is scored 0-10, and an overall score is calculated.

### Output

Results are logged to LangSmith and can be viewed in the LangSmith dashboard:
- Experiment name: `ai-school-agent-qa-{timestamp}`
- Each example is evaluated with detailed scores and explanations
- View results at: https://smith.langchain.com/

**Viewing Scores in LangSmith:**
1. Navigate to your experiment in the LangSmith dashboard
2. Switch from "Diff" view to **"Full"** view to see scores
3. Look for the **"llm_judge_score"** column or check the evaluator feedback section
4. Scores are normalized to 0-1 (multiply by 10 to get 0-10 scale)
5. Detailed sub-scores (accuracy, completeness, relevance, clarity, grounding) are in the feedback section
6. You can also click on individual runs to see detailed evaluation feedback

### Adding Your Own Dataset

1. Create a CSV file in `evals/ai_school_agent/data/` following the format above
2. Run the evaluation script with your CSV file
3. View results in LangSmith dashboard


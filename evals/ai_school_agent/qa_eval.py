#!/usr/bin/env python3
"""
Q&A Evaluation Script for AI School Agent

This script evaluates the AI School Agent using a CSV dataset with questions
and ground truth answers, using LLM-as-a-Judge for evaluation.

Usage:
    uv run eval-ai-school-agent --csv evals/ai_school_agent/data/ai_school_kb_qa_dataset.csv
    
CSV Format (supports two formats):
    1. AI School KB format: q,a,created_at,last_edited_at
    2. Standard format: question,ground_truth,category,difficulty,metadata
"""

import os
import sys
import asyncio
import csv
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langsmith import Client, RunEvaluator
from langsmith.evaluation import EvaluationResult
from langsmith.schemas import Example, Run
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# Set up clients
client = Client(
    api_key=os.getenv("LANGCHAIN_API_KEY"),
    api_url=os.getenv("LANGSMITH_ENDPOINT")
)
# LLM for evaluating ground truth match
evaluator_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def load_qa_dataset(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load Q&A dataset from CSV file.
    
    Supports two CSV formats:
    1. Standard format: question, ground_truth, category, difficulty, metadata
    2. AI School KB format: q, a, created_at, last_edited_at
    """
    examples = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle AI School KB format (q, a, created_at, last_edited_at)
            if "q" in row and "a" in row:
                question = row.get("q", "").strip()
                ground_truth = row.get("a", "").strip()
                
                # Build metadata from available columns
                metadata = {}
                if "created_at" in row and row["created_at"]:
                    metadata["created_at"] = row["created_at"].strip()
                if "last_edited_at" in row and row["last_edited_at"]:
                    metadata["last_edited_at"] = row["last_edited_at"].strip()
            
            # Handle standard format (question, ground_truth, category, difficulty, metadata)
            else:
                question = row.get("question", "").strip()
                ground_truth = row.get("ground_truth", "").strip()
                
                # Add optional metadata
                metadata = {}
                if "category" in row and row["category"]:
                    metadata["category"] = row["category"].strip()
                if "difficulty" in row and row["difficulty"]:
                    metadata["difficulty"] = row["difficulty"].strip()
                if "metadata" in row and row["metadata"]:
                    try:
                        metadata.update(json.loads(row["metadata"]))
                    except json.JSONDecodeError:
                        pass
            
            # Skip empty rows
            if not question or not ground_truth:
                continue
            
            example = {
                "inputs": {"question": question},
                "outputs": {"ground_truth": ground_truth},
            }
            
            if metadata:
                example["metadata"] = metadata
            
            examples.append(example)
    
    return examples


async def call_ai_school_agent(question: str, session_id: str = None) -> str:
    """
    Call the AI School Agent with a question.
    
    This function directly imports and calls the agent generator function
    to avoid HTTP overhead during evaluation.
    """
    # Import here to avoid circular dependencies
    from src.db.database import SessionLocal
    from src.routers.aiSchoolAgent.completion import generator
    from src.db.models import Account, ChatAppSession
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Find or create a test account for evaluation
        test_email = "eval@test.com"
        test_account = db.query(Account).filter(Account.email == test_email).first()
        
        if not test_account:
            print("⚠️  Creating test account for evaluation...")
            # Create a test account (you may need to adjust this based on your Account model)
            from src.deps import bcrypt_context
            import stripe
            
            # Try to create Stripe customer (may fail in test environment)
            stripe_customer_id = None
            try:
                from src.clients.stripe_client import create_stripe_customer
                stripe_customer_id = create_stripe_customer(test_email)
            except Exception as e:
                print(f"⚠️  Could not create Stripe customer: {e}")
                # For eval, we can proceed without Stripe if needed
            
            test_account = Account(
                email=test_email,
                hashed_password=bcrypt_context.hash("test_password_123"),
                stripe_customer_id=stripe_customer_id
            )
            db.add(test_account)
            db.commit()
            db.refresh(test_account)
            print(f"✅ Created test account: {test_account.id}")
        
        # Create a test session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Ensure session exists
        session_uuid = uuid.UUID(session_id)
        session = db.query(ChatAppSession).filter(
            ChatAppSession.session_id == session_uuid,
            ChatAppSession.account_id == test_account.id
        ).first()
        
        if not session:
            session = ChatAppSession(
                session_id=session_id,
                chat_app_id="eval",
                account_id=test_account.id,
                title="Evaluation Session"
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Create mock JWT
        mock_jwt = {
            'id': test_account.id,
            'email': test_account.email
        }
        
        # Collect the full response from the streaming generator
        full_response = ""
        async for chunk in generator(session_id, question, db, mock_jwt):
            # Parse the JSON chunks from the stream
            try:
                chunk_data = json.loads(chunk)
                if chunk_data.get("event") == "on_chat_model_stream":
                    full_response += chunk_data.get("data", "")
                elif chunk_data.get("event") == "on_chain_end":
                    # Final response
                    final_data = chunk_data.get("data", "")
                    if final_data:
                        full_response = final_data
            except json.JSONDecodeError:
                continue
        
        return full_response.strip()
    except Exception as e:
        print(f"❌ Error calling AI School Agent: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


class GroundTruthComparisonEvaluator(RunEvaluator):
    """Direct comparison evaluator that scores how accurately the output matches the ground truth"""
    
    def __init__(self):
        pass
    
    def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
        # IMPORTANT: This method MUST be called by LangSmith's evaluation framework
        # If you don't see "📊 Ground truth match:" messages, this method isn't being called
        run_id_str = str(run.id)[:8] if hasattr(run.id, '__str__') else str(run.id)[:8]
        print(f"  📊 [GROUND TRUTH] Starting evaluation for run {run_id_str}...")
        try:
            # Extract ground truth from example
            ground_truth = example.outputs.get("ground_truth", "").strip().lower()
            
            print(f"  📊 [GROUND TRUTH] Ground truth: {ground_truth[:50]}...")
            
            # Extract answer from run
            answer = ""
            if run.outputs:
                if isinstance(run.outputs, dict):
                    answer = run.outputs.get("output", "") or run.outputs.get("answer", "") or str(run.outputs)
                else:
                    answer = str(run.outputs)
            elif run.extra and "output" in run.extra:
                answer = str(run.extra["output"])
            
            answer = answer.strip().lower()
            
            if not answer:
                return EvaluationResult(
                    key="ground_truth_match",
                    score=0.0,
                    comment="No answer found in run outputs"
                )
            
            if not ground_truth:
                return EvaluationResult(
                    key="ground_truth_match",
                    score=0.0,
                    comment="No ground truth provided"
                )
            
            # Calculate similarity scores using multiple methods
            scores = {}
            
            # 1. Exact match (case-insensitive)
            exact_match = 1.0 if answer == ground_truth else 0.0
            scores["exact_match"] = exact_match
            
            # 2. Substring match - check if ground truth is contained in answer or vice versa
            if ground_truth in answer or answer in ground_truth:
                substring_score = min(len(ground_truth), len(answer)) / max(len(ground_truth), len(answer))
            else:
                substring_score = 0.0
            scores["substring_match"] = substring_score
            
            # 3. Word overlap - compare key words/phrases
            ground_truth_words = set(word for word in ground_truth.split() if len(word) > 2)
            answer_words = set(word for word in answer.split() if len(word) > 2)
            
            if ground_truth_words:
                word_overlap = len(ground_truth_words.intersection(answer_words)) / len(ground_truth_words)
            else:
                word_overlap = 0.0
            scores["word_overlap"] = word_overlap
            
            # 4. Key phrase extraction - look for important phrases (3+ words)
            def extract_phrases(text, n=3):
                words = text.split()
                return set(' '.join(words[i:i+n]) for i in range(len(words) - n + 1))
            
            ground_truth_phrases = extract_phrases(ground_truth)
            answer_phrases = extract_phrases(answer)
            
            if ground_truth_phrases:
                phrase_overlap = len(ground_truth_phrases.intersection(answer_phrases)) / len(ground_truth_phrases)
            else:
                phrase_overlap = 0.0
            scores["phrase_overlap"] = phrase_overlap
            
            # Calculate weighted overall score
            # Exact match gets highest weight, then phrase overlap, then word overlap
            overall_score = (
                exact_match * 0.4 +
                substring_score * 0.2 +
                phrase_overlap * 0.25 +
                word_overlap * 0.15
            )
            
            # Generate comment
            if exact_match == 1.0:
                comment = "Perfect match with ground truth"
            elif substring_score > 0.8:
                comment = f"High similarity: {substring_score:.2%} substring match"
            elif phrase_overlap > 0.5:
                comment = f"Moderate match: {phrase_overlap:.2%} phrase overlap, {word_overlap:.2%} word overlap"
            else:
                comment = f"Low match: {word_overlap:.2%} word overlap"
            
            print(f"  📊 Ground truth match: {overall_score:.3f} ({comment})")
            
            return EvaluationResult(
                key="ground_truth_match",
                score=overall_score,
                comment=comment,
                feedback={
                    "exact_match": exact_match,
                    "substring_match": substring_score,
                    "word_overlap": word_overlap,
                    "phrase_overlap": phrase_overlap,
                    "ground_truth_length": len(ground_truth),
                    "answer_length": len(answer)
                }
            )
            
        except Exception as e:
            print(f"Error in ground truth comparison: {e}")
            return EvaluationResult(
                key="ground_truth_match",
                score=0.0,
                comment=f"Evaluation error: {str(e)}"
            )


async def run_evaluation(csv_path: str = None, dataset_name: str = None, use_existing: bool = False):
    """Run evaluation on AI School Agent using CSV dataset or existing LangSmith dataset"""
    
    print("🚀 Starting AI School Agent Q&A Evaluation")
    print("=" * 60)
    
    # Handle dataset lookup/creation
    if use_existing and dataset_name:
        # Use existing dataset by name, skip CSV loading and example addition
        if csv_path:
            print(f"⚠️  Warning: --csv provided but --use-existing-dataset is set. Ignoring CSV and using existing dataset.")
        
        print(f"\n📊 Looking up existing LangSmith dataset: {dataset_name}")
        try:
            datasets = list(client.list_datasets(dataset_name=dataset_name))
            if datasets:
                dataset = datasets[0]
                print(f"✅ Found existing dataset: {dataset.name} (ID: {dataset.id})")
                print(f"⏭️  Skipping CSV loading and example addition (using existing dataset)")
            else:
                print(f"❌ Dataset '{dataset_name}' not found!")
                print("Available datasets:")
                all_datasets = list(client.list_datasets())
                for ds in all_datasets[:10]:  # Show first 10
                    print(f"  - {ds.name}")
                if len(all_datasets) > 10:
                    print(f"  ... and {len(all_datasets) - 10} more")
                return
        except Exception as e:
            print(f"❌ Error looking up dataset: {e}")
            return
    elif csv_path:
        # Load dataset from CSV and create/update LangSmith dataset
        print(f"\n📂 Loading dataset from: {csv_path}")
        examples = load_qa_dataset(csv_path)
        print(f"✅ Loaded {len(examples)} examples")
        
        if not examples:
            print("❌ No examples found in CSV file!")
            return
        
        # Create or get dataset in LangSmith
        if dataset_name is None:
            dataset_name = f"ai-school-agent-qa-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        print(f"\n📊 Creating/updating LangSmith dataset: {dataset_name}")
        try:
            # Try to find existing dataset first
            datasets = list(client.list_datasets(dataset_name=dataset_name))
            if datasets:
                dataset = datasets[0]
                print(f"✅ Using existing dataset: {dataset.name}")
            else:
                # Create new dataset
                dataset = client.create_dataset(
                    dataset_name=dataset_name,
                    description="Q&A evaluation dataset for AI School Agent"
                )
                print(f"✅ Created new dataset: {dataset.name}")
        except Exception as e:
            print(f"❌ Error with dataset: {e}")
            raise
        
        # Add examples to dataset
        print(f"\n➕ Adding examples to dataset...")
        added_count = 0
        skipped_count = 0
        for example in examples:
            try:
                client.create_example(
                    inputs=example["inputs"],
                    outputs=example["outputs"],
                    dataset_id=dataset.id,
                    metadata=example.get("metadata", {})
                )
                added_count += 1
            except Exception as e:
                # Example might already exist
                skipped_count += 1
        
        print(f"✅ Added {added_count} examples, skipped {skipped_count} duplicates")
    else:
        print("❌ Error: Must provide either --csv or --use-existing-dataset with --dataset-name")
        return
    
    print(f"✅ Dataset ready: {dataset.name} (ID: {dataset.id})")
    
    # Define the function to evaluate
    async def ai_school_agent_function(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper function for the AI School Agent"""
        question = inputs.get("question", "")
        session_id = str(uuid.uuid4())
        
        print(f"  🤖 Processing: {question[:50]}...")
        answer = await call_ai_school_agent(question, session_id)
        
        return {"output": answer}
    
    # Create function-based evaluator for ground truth accuracy
    # LangSmith's client.aevaluate() works with function-based evaluators
    
    def ground_truth_evaluator_function(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        """
        Ground Truth Accuracy Evaluator (LLM-based)
        
        Uses an LLM to assess how accurately the answer matches the ground truth (0-1 scale).
        This score will appear in LangSmith dashboard and can be tracked over time.
        """
        print(f"  📊 [GROUND TRUTH] Starting LLM evaluation...")
        try:
            question = inputs.get("question", "")
            ground_truth = reference_outputs.get("ground_truth", "").strip()
            answer = (outputs.get("output", "") or outputs.get("answer", "")).strip()
            
            if not answer:
                return {
                    "key": "ground_truth_match",
                    "score": 0.0,
                    "comment": "No answer found in outputs"
                }
            
            if not ground_truth:
                return {
                    "key": "ground_truth_match",
                    "score": 0.0,
                    "comment": "No ground truth provided"
                }
            
            # Create prompt for LLM evaluator
            evaluation_prompt = f"""You are an expert evaluator assessing how well an AI assistant's answer matches the expected ground truth answer.

Question: {question}

Ground Truth Answer: {ground_truth}

AI Assistant Answer: {answer}

Evaluate how accurately the AI assistant's answer matches the ground truth. Consider:
- Does the answer convey the same information as the ground truth?
- Are the key facts and details correct?
- Is the answer semantically equivalent even if worded differently?
- Are there any important omissions or additions?

Return your evaluation in JSON format:
{{
    "score": <0.0-1.0>,
    "explanation": "<brief explanation of how well the answer matches the ground truth>"
}}

Score guidelines:
- 1.0: Perfect match - answer is semantically identical to ground truth
- 0.8-0.9: Very close match - minor differences in wording but same meaning
- 0.6-0.7: Good match - core information correct but some differences
- 0.4-0.5: Partial match - some correct information but missing or incorrect details
- 0.2-0.3: Poor match - minimal overlap with ground truth
- 0.0-0.1: No match - answer is incorrect or unrelated

Return only valid JSON, no other text."""

            # Get evaluation from LLM
            response = evaluator_llm.invoke(evaluation_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks)
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                eval_data = json.loads(response_text)
                score = float(eval_data.get("score", 0.0))
                explanation = eval_data.get("explanation", "")
                
                # Ensure score is between 0 and 1
                score = max(0.0, min(1.0, score))
                
                print(f"  📊 [GROUND TRUTH] LLM accuracy score: {score:.3f}")
                print(f"     Explanation: {explanation[:100]}...")
                
                # LangSmith expects function-based evaluators to return a dict with:
                # - 'key': the feedback key name
                # - 'score': the numeric score (0-1)
                # - Optional: 'comment' or other fields
                return {
                    "key": "ground_truth_match",
                    "score": score,
                    "comment": explanation
                }
            except json.JSONDecodeError as e:
                print(f"  ⚠️  [GROUND TRUTH] Failed to parse JSON: {e}")
                print(f"     Response: {response_text[:200]}...")
                # Fallback: try to extract a score from the text
                import re
                score_match = re.search(r'"score":\s*([\d.]+)', response_text)
                if score_match:
                    score = float(score_match.group(1))
                    score = max(0.0, min(1.0, score))
                    return {
                        "key": "ground_truth_match",
                        "score": score,
                        "comment": f"Parsed score from response (JSON parse failed)"
                    }
                return {
                    "key": "ground_truth_match",
                    "score": 0.5,
                    "comment": f"Could not parse evaluator response"
                }
        except Exception as e:
            print(f"  ❌ [GROUND TRUTH] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "key": "ground_truth_match",
                "score": 0.0,
                "comment": f"Evaluation error: {str(e)}"
            }
    
    # Run evaluation
    print(f"\n🔍 Running evaluation...")
    print("This may take a while depending on the number of examples...")
    print(f"  📋 Using evaluator:")
    print(f"     - Ground Truth Accuracy (key: ground_truth_match)")
    print(f"     This evaluator scores how accurately the answer matches the ground truth (0-1 scale)")
    
    try:
        # Use async evaluate() which handles async functions
        # Use dataset name for evaluation
        eval_dataset_name = dataset.name
        
        # Construct project name from experiment prefix
        project_name = f"ai-school-agent-qa-{datetime.now().strftime('%Y%m%d')}"
        
        print(f"  📋 Project name will be: {project_name}")
        print(f"  ⏳ Running evaluation (this may take a while)...")
        print(f"  ⚠️  IMPORTANT: Watch for evaluator messages:")
        print(f"     - '📊 [GROUND TRUTH] Starting evaluation...'")
        
        results = await client.aevaluate(
            ai_school_agent_function,
            data=eval_dataset_name,
            evaluators=[ground_truth_evaluator_function],
            experiment_prefix="ai-school-agent-qa",
            max_concurrency=5,  # Limit concurrent requests
        )
        
        print(f"\n✅ Evaluation complete!")
        
        # Extract project name from results or use constructed one
        if isinstance(results, dict):
            eval_id = results.get('id', 'N/A')
            result_project = results.get('project_name', None)
        else:
            eval_id = getattr(results, 'id', 'N/A')
            result_project = getattr(results, 'project_name', None) if hasattr(results, 'project_name') else None
        
        # Use result project name if available, otherwise try to find it
        if result_project and result_project != 'N/A':
            project_name = result_project
        else:
            # Try to find the project by listing recent projects
            try:
                projects = list(client.list_projects())
                matching = [p for p in projects if 'ai-school-agent-qa' in p.name]
                if matching:
                    project_name = matching[0].name
                    print(f"  📋 Found project: {project_name}")
            except:
                pass
        
        print(f"📊 Evaluation ID: {eval_id}")
        print(f"📈 Dataset: {dataset.name}")
        print(f"📋 Project Name: {project_name}")
        
        # Verify evaluators ran by checking for feedback
        print(f"\n🔍 Verifying evaluators ran...")
        try:
            # Get a sample run to check for feedback
            sample_runs = list(client.list_runs(project_name=project_name, limit=5))
            if sample_runs:
                feedback_found = 0
                for run in sample_runs:
                    run_id_str = str(run.id)[:8] if hasattr(run.id, '__str__') else str(run.id)[:8]
                    feedback = list(client.list_feedback(run_ids=[run.id]))
                    if feedback:
                        feedback_found += len(feedback)
                        print(f"   ✅ Run {run_id_str}... has {len(feedback)} feedback entries")
                        for fb in feedback:
                            score_str = f"{fb.score:.3f}" if fb.score is not None else "N/A"
                            comment_preview = (fb.comment[:40] + "...") if fb.comment and len(fb.comment) > 40 else (fb.comment or "No comment")
                            print(f"      - Key: {fb.key}, Score: {score_str}, Comment: {comment_preview}")
                            # Also check feedback value if score is None
                            if fb.score is None and hasattr(fb, 'value'):
                                print(f"         Value: {fb.value}")
                
                if feedback_found == 0:
                    print(f"   ⚠️  WARNING: No feedback found! Evaluators may not have run.")
                    print(f"   💡 Check the evaluation logs above for evaluator messages:")
                    print(f"      - '🔍 [LLM JUDGE] Starting evaluation...'")
                    print(f"      - '📊 [GROUND TRUTH] Starting evaluation...'")
                    print(f"   💡 If you don't see these messages, evaluators didn't run.")
                else:
                    print(f"   ✅ Found {feedback_found} total feedback entries across sample runs")
        except Exception as e:
            print(f"   ⚠️  Could not verify feedback: {e}")
            import traceback
            traceback.print_exc()
        print(f"\n📝 To view scores in LangSmith dashboard:")
        print(f"   1. Go to your experiment: https://smith.langchain.com/")
        print(f"   2. Switch from 'Diff' to 'Full' view (top right)")
        print(f"   3. Click the column configuration icon (⚙️) or 'Display' dropdown")
        print(f"   4. Click '+ Column' and add these columns:")
        print(f"      - feedback.llm_judge_score.score (LLM-as-Judge score)")
        print(f"      - feedback.ground_truth_match.score (Direct ground truth match)")
        print(f"   5. Both evaluators run automatically:")
        print(f"      - LLM-as-Judge: Uses AI to evaluate answer quality (0-1)")
        print(f"      - Ground Truth Match: Direct comparison with reference (0-1)")
        print(f"\n💡 TROUBLESHOOTING:")
        print(f"   - Check console output for '🔍 Evaluating:' and '📊 Ground truth match' messages")
        print(f"   - Verify OPENAI_API_KEY is set (required for LLM-as-a-Judge)")
        print(f"\n🔗 View results in LangSmith: https://smith.langchain.com/")
        
        return results
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Evaluate AI School Agent using Q&A dataset"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to CSV file with questions and ground truth answers (optional if using existing dataset)"
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default=None,
        help="Name for the LangSmith dataset (default: auto-generated from CSV, or required with --use-existing-dataset)"
    )
    parser.add_argument(
        "--use-existing-dataset",
        action="store_true",
        help="Use an existing LangSmith dataset by name (requires --dataset-name). Skips CSV loading."
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.use_existing_dataset:
        if not args.dataset_name:
            print("❌ Error: --use-existing-dataset requires --dataset-name")
            sys.exit(1)
        # Skip CSV validation when using existing dataset
        # CSV is optional and will be ignored if provided
    else:
        if not args.csv:
            print("❌ Error: --csv is required unless using --use-existing-dataset")
            sys.exit(1)
        # Validate CSV file exists
        if not os.path.exists(args.csv):
            print(f"❌ Error: CSV file not found: {args.csv}")
            sys.exit(1)
    
    # Check environment variables
    if not os.getenv("LANGCHAIN_API_KEY") and not os.getenv("LANGSMITH_API_KEY"):
        print("⚠️  Warning: LANGCHAIN_API_KEY or LANGSMITH_API_KEY not set. Results may not be logged to LangSmith.")
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not set. Required for LLM-as-a-Judge evaluation.")
        sys.exit(1)
    
    # Run evaluation
    asyncio.run(run_evaluation(args.csv, args.dataset_name, args.use_existing_dataset))


if __name__ == "__main__":
    main()


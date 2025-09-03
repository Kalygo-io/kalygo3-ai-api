#!/usr/bin/env python3
"""
LangSmith Evaluation Quick Start Demo Script

This script demonstrates the power of LangSmith's evaluation framework
for an audience of 20-30 people. It showcases:

1. Creating a dataset with examples
2. Running evaluations with different evaluator types
3. Comparing results
4. Using built-in and custom evaluators

Based on: https://docs.smith.langchain.com/evaluation?mode=sdk
"""

from datetime import datetime
import os
import asyncio
from typing import Dict, List, Any
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LangSmith components
from langsmith import Client, RunEvaluator
from langsmith.evaluation import EvaluationResult, run_evaluator
from langsmith.schemas import Example, Run, Dataset

# Set up LangSmith client
print('os.getenv("LANGSMITH_API_KEY"):', os.getenv("LANGSMITH_API_KEY"))
print('os.getenv("LANGSMITH_ENDPOINT"):', os.getenv("LANGSMITH_ENDPOINT"))

client = Client(
    api_key=os.getenv("LANGSMITH_API_KEY"),
    api_url=os.getenv("LANGSMITH_ENDPOINT")
)

def create_demo_dataset():
    """Create a demo dataset for evaluation"""
    print("🚀 Creating demo dataset...")
    
    # Create examples for a Q&A chatbot
    examples = [
        Example(
            id=uuid.uuid4(),
            dataset_id="28821816-55ea-4923-97db-7cb2a0ee08ba",
            type="llm",
            inputs={"question": "What is the capital of France?"},
            outputs={"answer": "The capital of France is Paris."},
            metadata={"category": "geography", "difficulty": "easy"}
        ),
        Example(
            id=uuid.uuid4(),
            dataset_id="28821816-55ea-4923-97db-7cb2a0ee08ba",
            type="llm",
            inputs={"question": "How do you make a chocolate cake?"},
            outputs={"answer": "To make a chocolate cake, you need flour, sugar, cocoa powder, eggs, milk, and butter. Mix dry ingredients, add wet ingredients, bake at 350°F for 25-30 minutes."},
            metadata={"category": "cooking", "difficulty": "medium"}
        ),
        Example(
            id=uuid.uuid4(),
            dataset_id="28821816-55ea-4923-97db-7cb2a0ee08ba",
            type="llm",
            inputs={"question": "What is the meaning of life?"},
            outputs={"answer": "The meaning of life is a philosophical question that has been debated for centuries. Different cultures and philosophies offer various perspectives on this profound question."},
            metadata={"category": "philosophy", "difficulty": "hard"}
        ),
        Example(
            id=uuid.uuid4(),
            dataset_id="28821816-55ea-4923-97db-7cb2a0ee08ba",
            type="llm",
            inputs={"question": "What is 2 + 2?"},
            outputs={"answer": "2 + 2 equals 4."},
            metadata={"category": "math", "difficulty": "easy"}
        ),
        Example(
            id=uuid.uuid4(),
            dataset_id="28821816-55ea-4923-97db-7cb2a0ee08ba",
            type="llm",
            inputs={"question": "Explain quantum computing in simple terms"},
            outputs={"answer": "Quantum computing uses quantum mechanical phenomena like superposition and entanglement to process information. Instead of classical bits (0 or 1), it uses quantum bits (qubits) that can exist in multiple states simultaneously."},
            metadata={"category": "technology", "difficulty": "hard"}
        )
    ]
    
    # # Create the dataset
    # dataset = client.create_dataset(
    #     dataset_name="demo-evaluation-dataset",
    #     description="Demo dataset for showcasing LangSmith evaluation capabilities"
    # )

    dataset = client.read_dataset(dataset_name="demo-evaluation-dataset")
    
    # # Add examples to the dataset
    # for example in examples:
    #     client.create_example(
    #         inputs=example.inputs,
    #         outputs=example.outputs,
    #         dataset_id=dataset.id,
    #         metadata=example.metadata
    #     )
    
    # print(f"✅ Created dataset: {dataset.name} (ID: {dataset.id})")
    # print(f"📊 Added {len(examples)} examples")
    return dataset

def create_custom_evaluators():
    """Create custom evaluators for different aspects of responses"""
    
    class AnswerLengthEvaluator(RunEvaluator):
        """Evaluates if the answer length is appropriate for the question difficulty"""
        
        def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
            answer = run.outputs.get("answer", "")
            difficulty = example.metadata.get("difficulty", "medium")
            
            # Define expected length ranges by difficulty
            expected_lengths = {
                "easy": (10, 50),
                "medium": (30, 100),
                "hard": (50, 200)
            }
            
            min_len, max_len = expected_lengths.get(difficulty, (20, 100))
            actual_len = len(answer)
            
            if min_len <= actual_len <= max_len:
                score = 1.0
                comment = f"Perfect length ({actual_len} chars) for {difficulty} question"
            elif actual_len < min_len:
                score = 0.5
                comment = f"Too short ({actual_len} chars) for {difficulty} question (expected {min_len}+)"
            else:
                score = 0.7
                comment = f"Too long ({actual_len} chars) for {difficulty} question (expected {max_len}-)"
            
            return EvaluationResult(
                key="answer_length",
                score=score,
                comment=comment
            )
    
    class AnswerRelevanceEvaluator(RunEvaluator):
        """Evaluates if the answer is relevant to the question"""
        
        def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
            question = example.inputs.get("question", "").lower()
            answer = run.outputs.get("answer", "").lower()
            
            # Simple keyword matching for demo purposes
            # In production, you'd use more sophisticated NLP
            question_keywords = set(question.split())
            answer_keywords = set(answer.split())
            
            # Remove common words
            common_words = {"what", "is", "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            question_keywords -= common_words
            answer_keywords -= common_words
            
            if not question_keywords:
                score = 0.5
                comment = "Question has no meaningful keywords"
            else:
                overlap = len(question_keywords.intersection(answer_keywords))
                score = min(1.0, overlap / len(question_keywords))
                comment = f"Keyword overlap: {overlap}/{len(question_keywords)}"
            
            return EvaluationResult(
                key="answer_relevance",
                score=score,
                comment=comment
            )
    
    class CategoryAccuracyEvaluator(RunEvaluator):
        """Evaluates if the answer matches the expected category"""
        
        def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
            expected_category = example.metadata.get("category", "")
            answer = run.outputs.get("answer", "").lower()
            
            # Define category keywords
            category_keywords = {
                "geography": ["country", "city", "capital", "location", "place", "map"],
                "cooking": ["recipe", "ingredients", "bake", "cook", "food", "kitchen"],
                "philosophy": ["meaning", "purpose", "existence", "philosophical", "question"],
                "math": ["equals", "calculation", "number", "equation", "sum"],
                "technology": ["computer", "quantum", "technology", "system", "digital"]
            }
            
            if expected_category not in category_keywords:
                score = 0.5
                comment = f"Unknown category: {expected_category}"
            else:
                keywords = category_keywords[expected_category]
                matches = sum(1 for keyword in keywords if keyword in answer)
                score = min(1.0, matches / len(keywords))
                comment = f"Category match: {matches}/{len(keywords)} keywords found"
            
            return EvaluationResult(
                key="category_accuracy",
                score=score,
                comment=comment
            )
    
    return [
        AnswerLengthEvaluator(),
        AnswerRelevanceEvaluator(),
        CategoryAccuracyEvaluator()
    ]

def simulate_llm_responses(examples: List[Example]) -> List[Run]:
    """Simulate LLM responses for demo purposes"""
    print("🤖 Simulating LLM responses...")
    
    # Simulate different quality responses
    simulated_responses = [
        "The capital of France is Paris.",
        "To make a chocolate cake, you need flour, sugar, cocoa powder, eggs, milk, and butter. Mix dry ingredients, add wet ingredients, bake at 350°F for 25-30 minutes.",
        "The meaning of life is a philosophical question that has been debated for centuries. Different cultures and philosophies offer various perspectives on this profound question.",
        "2 + 2 equals 4.",
        "Quantum computing uses quantum mechanical phenomena like superposition and entanglement to process information. Instead of classical bits (0 or 1), it uses quantum bits (qubits) that can exist in multiple states simultaneously."
    ]
    
    runs = []
    for i, example in enumerate(examples):
        run = Run(
            start_time=datetime.now(),
            id=uuid.uuid4(),
            inputs=example.inputs,
            outputs={"answer": simulated_responses[i]},
            run_type="llm",
            name="Demo Q&A Bot"
        )
        runs.append(run)
    
    print(f"✅ Created {len(runs)} simulated runs")
    return runs

def run_evaluations(dataset: Dataset, examples: List[Example], evaluators, runs):
    """Run evaluations on the dataset"""
    print("🔍 Running evaluations...")
    
    results = []
    for run in runs:
        run_results = []
        for evaluator in evaluators:
            try:
                result = evaluator.evaluate_run(run, examples[0])  # Using first example for demo
                run_results.append(result)
            except Exception as e:
                print(f"⚠️  Error running evaluator {evaluator.__class__.__name__}: {e}")
        
        results.append(run_results)
    
    print(f"✅ Completed evaluations for {len(runs)} runs")
    return results

def display_results(results, runs):
    """Display evaluation results in a formatted way"""
    print("\n" + "="*80)
    print("📊 EVALUATION RESULTS")
    print("="*80)
    
    for i, (run, run_results) in enumerate(zip(runs, results)):
        print(f"\n🔹 Run {i+1}: {run.outputs.get('answer', '')[:50]}...")
        print("-" * 60)
        
        for result in run_results:
            if hasattr(result, 'key') and hasattr(result, 'score'):
                print(f"  {result.key}: {result.score:.2f} - {getattr(result, 'comment', 'No comment')}")
            else:
                print(f"  Result: {result}")
    
    # Calculate average scores
    print("\n" + "="*80)
    print("📈 SUMMARY STATISTICS")
    print("="*80)
    
    all_scores = {}
    for run_results in results:
        for result in run_results:
            if hasattr(result, 'key') and hasattr(result, 'score'):
                key = result.key
                if key not in all_scores:
                    all_scores[key] = []
                all_scores[key].append(result.score)
    
    for key, scores in all_scores.items():
        avg_score = sum(scores) / len(scores)
        print(f"  {key}: {avg_score:.3f} (n={len(scores)})")

def main():
    """Main demo function"""
    print("🎯 LangSmith Evaluation Demo")
    print("="*50)
    
    try:
        # Check if LangSmith API key is set
        if not os.getenv("LANGSMITH_API_KEY"):
            print("⚠️  Warning: LANGSMITH_API_KEY not set. Some features may not work.")
            print("   Set it to run full evaluations with LangSmith.")
        
        # Create dataset
        dataset = create_demo_dataset()
        
        # Get examples from dataset
        examples = list(client.list_examples(dataset_id=dataset.id))
        
        # Create evaluators
        evaluators = create_custom_evaluators()
        print(f"✅ Created {len(evaluators)} custom evaluators")
        
        # Simulate runs
        runs = simulate_llm_responses(examples)
        
        # Run evaluations
        results = run_evaluations(dataset, examples, evaluators, runs)
        
        # Display results
        display_results(results, runs)
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        print("This might be due to missing API keys or network issues.")

if __name__ == "__main__":
    main()

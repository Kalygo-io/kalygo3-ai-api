#!/usr/bin/env python3
"""
Advanced LangSmith Evaluation Demo

This script demonstrates advanced evaluation techniques including:
1. LLM-as-judge evaluators
2. Pairwise comparisons
3. Regression testing
4. Custom scoring functions
5. Batch evaluation processing

Perfect for demonstrating the full power of LangSmith evaluations.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Import LangSmith components
from langsmith import Client, RunEvaluator
from langsmith.evaluation import EvaluationResult, run_evaluator
from langsmith.schemas import Example, Run
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Set up clients
client = Client()
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def create_advanced_dataset():
    """Create a more sophisticated dataset for advanced evaluations"""
    print("🚀 Creating advanced evaluation dataset...")
    
    examples = [
        {
            "inputs": {"question": "Explain the benefits of renewable energy"},
            "outputs": {"answer": "Renewable energy sources like solar, wind, and hydroelectric power offer numerous benefits including reduced greenhouse gas emissions, lower operating costs over time, energy independence, and job creation in the green economy."},
            "metadata": {"category": "environment", "difficulty": "medium", "expected_aspects": ["emissions", "costs", "independence", "jobs"]}
        },
        {
            "inputs": {"question": "What are the main differences between Python and JavaScript?"},
            "outputs": {"answer": "Python is a high-level, interpreted programming language known for its readability and simplicity, while JavaScript is primarily used for web development and runs in browsers. Python has strong typing and is great for data science, while JavaScript is dynamically typed and excels at interactive web applications."},
            "metadata": {"category": "programming", "difficulty": "medium", "expected_aspects": ["typing", "use_cases", "syntax", "performance"]}
        },
        {
            "inputs": {"question": "How does machine learning work?"},
            "outputs": {"answer": "Machine learning is a subset of artificial intelligence where algorithms learn patterns from data to make predictions or decisions without being explicitly programmed. It involves training models on historical data, validating performance, and deploying for inference on new data."},
            "metadata": {"category": "ai", "difficulty": "hard", "expected_aspects": ["algorithms", "training", "validation", "deployment"]}
        }
    ]
    
    # Create the dataset
    dataset = client.create_dataset(
        dataset_name="advanced-eval-dataset",
        description="Advanced evaluation dataset for sophisticated testing scenarios"
    )
    
    # Add examples to the dataset
    for example in examples:
        client.create_example(
            inputs=example["inputs"],
            outputs=example["outputs"],
            dataset_id=dataset.id,
            metadata=example["metadata"]
        )
    
    print(f"✅ Created advanced dataset: {dataset.name}")
    return dataset

class LLMAsJudgeEvaluator(RunEvaluator):
    """LLM-as-judge evaluator for assessing answer quality"""
    
    def __init__(self, evaluation_criteria: str):
        self.evaluation_criteria = evaluation_criteria
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert evaluator. Rate the quality of the answer based on the given criteria."),
            ("human", """
            Question: {question}
            Answer: {answer}
            Evaluation Criteria: {criteria}
            
            Please rate the answer from 1-10 and provide a brief explanation.
            Return your response in JSON format:
            {{"score": <1-10>, "explanation": "<your reasoning>"}}
            """)
        ])
    
    def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
        try:
            # Format the prompt
            prompt = self.prompt_template.format_messages(
                question=example.inputs.get("question", ""),
                answer=run.outputs.get("answer", ""),
                criteria=self.evaluation_criteria
            )
            
            # Get LLM response
            response = llm.invoke(prompt)
            content = response.content
            
            # Parse JSON response
            try:
                result = json.loads(content)
                score = result.get("score", 5) / 10.0  # Normalize to 0-1
                explanation = result.get("explanation", "No explanation provided")
            except json.JSONDecodeError:
                score = 0.5
                explanation = "Failed to parse LLM response"
            
            return EvaluationResult(
                key="llm_judge_quality",
                score=score,
                comment=explanation
            )
            
        except Exception as e:
            return EvaluationResult(
                key="llm_judge_quality",
                score=0.5,
                comment=f"Evaluation failed: {str(e)}"
            )

class AspectCoverageEvaluator(RunEvaluator):
    """Evaluates how well the answer covers expected aspects"""
    
    def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
        expected_aspects = example.metadata.get("expected_aspects", [])
        if not expected_aspects:
            return EvaluationResult(
                key="aspect_coverage",
                score=0.5,
                comment="No expected aspects defined"
            )
        
        answer = run.outputs.get("answer", "").lower()
        covered_aspects = []
        
        for aspect in expected_aspects:
            if aspect.lower() in answer:
                covered_aspects.append(aspect)
        
        coverage_score = len(covered_aspects) / len(expected_aspects)
        
        return EvaluationResult(
            key="aspect_coverage",
            score=coverage_score,
            comment=f"Covered {len(covered_aspects)}/{len(expected_aspects)} aspects: {', '.join(covered_aspects)}"
        )

class PairwiseComparisonEvaluator(RunEvaluator):
    """Compares two different model responses to the same question"""
    
    def __init__(self, baseline_run: Run):
        self.baseline_run = baseline_run
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert evaluator comparing two answers to the same question."),
            ("human", """
            Question: {question}
            
            Answer A: {answer_a}
            Answer B: {answer_b}
            
            Which answer is better? Consider clarity, accuracy, completeness, and helpfulness.
            Return your response in JSON format:
            {{"winner": "A" or "B", "reasoning": "<your explanation>", "confidence": <0.0-1.0>}}
            """)
        ])
    
    def evaluate_run(self, run: Run, example: Example) -> EvaluationResult:
        try:
            # Format the prompt
            prompt = self.prompt_template.format_messages(
                question=example.inputs.get("question", ""),
                answer_a=self.baseline_run.outputs.get("answer", ""),
                answer_b=run.outputs.get("answer", "")
            )
            
            # Get LLM response
            response = llm.invoke(prompt)
            content = response.content
            
            # Parse JSON response
            try:
                result = json.loads(content)
                winner = result.get("winner", "B")
                confidence = result.get("confidence", 0.5)
                reasoning = result.get("reasoning", "No reasoning provided")
                
                # Score based on whether this run won
                score = confidence if winner == "B" else (1.0 - confidence)
                
            except json.JSONDecodeError:
                score = 0.5
                reasoning = "Failed to parse LLM response"
            
            return EvaluationResult(
                key="pairwise_comparison",
                score=score,
                comment=f"Winner: {winner}, Confidence: {confidence:.2f}, Reasoning: {reasoning}"
            )
            
        except Exception as e:
            return EvaluationResult(
                key="pairwise_comparison",
                score=0.5,
                comment=f"Comparison failed: {str(e)}"
            )

def create_advanced_evaluators():
    """Create advanced evaluators for sophisticated testing"""
    
    evaluators = [
        LLMAsJudgeEvaluator("Clarity, accuracy, completeness, and helpfulness"),
        AspectCoverageEvaluator()
    ]
    
    print(f"✅ Created {len(evaluators)} advanced evaluators")
    return evaluators

def simulate_competing_models(examples: List[Example]) -> List[Run]:
    """Simulate responses from different model versions"""
    print("🤖 Simulating competing model responses...")
    
    # Model A responses (baseline)
    model_a_responses = [
        "Renewable energy is good for the environment. It helps reduce pollution and creates jobs.",
        "Python is easier to learn than JavaScript. It has simpler syntax and is good for beginners.",
        "Machine learning uses algorithms to find patterns in data and make predictions."
    ]
    
    # Model B responses (improved version)
    model_b_responses = [
        "Renewable energy sources like solar, wind, and hydroelectric power offer numerous benefits including reduced greenhouse gas emissions, lower operating costs over time, energy independence, and job creation in the green economy. Additionally, they provide sustainable energy solutions that don't deplete natural resources.",
        "Python is a high-level, interpreted programming language known for its readability and simplicity, while JavaScript is primarily used for web development and runs in browsers. Python has strong typing and is great for data science, while JavaScript is dynamically typed and excels at interactive web applications.",
        "Machine learning is a subset of artificial intelligence where algorithms learn patterns from data to make predictions or decisions without being explicitly programmed. It involves training models on historical data, validating performance, and deploying for inference on new data. The process includes data preprocessing, feature engineering, model selection, and hyperparameter tuning."
    ]
    
    runs = []
    
    # Create baseline runs (Model A)
    for i, example in enumerate(examples):
        run = Run(
            id=f"model-a-run-{i}",
            inputs=example.inputs,
            outputs={"answer": model_a_responses[i]},
            run_type="llm",
            name="Model A (Baseline)",
            metadata={"model_version": "A", "baseline": True}
        )
        runs.append(run)
    
    # Create improved runs (Model B)
    for i, example in enumerate(examples):
        run = Run(
            id=f"model-b-run-{i}",
            inputs=example.inputs,
            outputs={"answer": model_b_responses[i]},
            run_type="llm",
            name="Model B (Improved)",
            metadata={"model_version": "B", "baseline": False}
        )
        runs.append(run)
    
    print(f"✅ Created {len(runs)} runs (2 models × {len(examples)} examples)")
    return runs

def run_advanced_evaluations(dataset, evaluators, runs):
    """Run advanced evaluations including pairwise comparisons"""
    print("🔍 Running advanced evaluations...")
    
    results = []
    
    # Get baseline runs
    baseline_runs = [run for run in runs if run.metadata.get("baseline", False)]
    
    for run in runs:
        run_results = []
        
        # Run standard evaluators
        for evaluator in evaluators:
            try:
                result = run_evaluator(evaluator, run, dataset.examples[0])
                run_results.append(result)
            except Exception as e:
                print(f"⚠️  Error running evaluator {evaluator.__class__.__name__}: {e}")
        
        # Run pairwise comparison if this is not a baseline run
        if not run.metadata.get("baseline", False):
            # Find corresponding baseline run
            baseline_run = next((b for b in baseline_runs if b.inputs == run.inputs), None)
            if baseline_run:
                pairwise_evaluator = PairwiseComparisonEvaluator(baseline_run)
                try:
                    result = run_evaluator(pairwise_evaluator, run, dataset.examples[0])
                    run_results.append(result)
                except Exception as e:
                    print(f"⚠️  Error running pairwise evaluator: {e}")
        
        results.append(run_results)
    
    print(f"✅ Completed advanced evaluations for {len(runs)} runs")
    return results

def display_advanced_results(results, runs):
    """Display advanced evaluation results with model comparison"""
    print("\n" + "="*100)
    print("📊 ADVANCED EVALUATION RESULTS")
    print("="*100)
    
    # Group results by model
    baseline_results = []
    improved_results = []
    
    for run, run_results in zip(runs, results):
        if run.metadata.get("baseline", False):
            baseline_results.append((run, run_results))
        else:
            improved_results.append((run, run_results))
    
    # Display baseline model results
    print("\n🔹 MODEL A (Baseline) Results:")
    print("-" * 60)
    for i, (run, run_results) in enumerate(baseline_results):
        print(f"\n  Example {i+1}: {run.outputs.get('answer', '')[:60]}...")
        for result in run_results:
            if hasattr(result, 'key') and hasattr(result, 'score'):
                print(f"    {result.key}: {result.score:.3f} - {getattr(result, 'comment', '')[:80]}...")
    
    # Display improved model results
    print("\n🔹 MODEL B (Improved) Results:")
    print("-" * 60)
    for i, (run, run_results) in enumerate(improved_results):
        print(f"\n  Example {i+1}: {run.outputs.get('answer', '')[:60]}...")
        for result in run_results:
            if hasattr(result, 'key') and hasattr(result, 'score'):
                print(f"    {result.key}: {result.score:.3f} - {getattr(result, 'comment', '')[:80]}...")
    
    # Calculate improvement metrics
    print("\n" + "="*100)
    print("📈 IMPROVEMENT ANALYSIS")
    print("="*100)
    
    # Compare scores between models
    for evaluator_type in ["llm_judge_quality", "aspect_coverage"]:
        baseline_scores = []
        improved_scores = []
        
        for run, run_results in zip(runs, results):
            for result in run_results:
                if result.key == evaluator_type:
                    if run.metadata.get("baseline", False):
                        baseline_scores.append(result.score)
                    else:
                        improved_scores.append(result.score)
        
        if baseline_scores and improved_scores:
            avg_baseline = sum(baseline_scores) / len(baseline_scores)
            avg_improved = sum(improved_scores) / len(improved_scores)
            improvement = ((avg_improved - avg_baseline) / avg_baseline) * 100
            
            print(f"\n  {evaluator_type}:")
            print(f"    Baseline: {avg_baseline:.3f}")
            print(f"    Improved: {avg_improved:.3f}")
            print(f"    Improvement: {improvement:+.1f}%")

def main():
    """Main advanced demo function"""
    print("🎯 Advanced LangSmith Evaluation Demo")
    print("="*60)
    
    try:
        # Check if required environment variables are set
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  Warning: OPENAI_API_KEY not set. LLM-as-judge evaluations will not work.")
            print("   Set it to run full advanced evaluations.")
        
        if not os.getenv("LANGCHAIN_API_KEY"):
            print("⚠️  Warning: LANGCHAIN_API_KEY not set. Some features may not work.")
            print("   Set it to run full evaluations with LangSmith.")
        
        # Create advanced dataset
        dataset = create_advanced_dataset()
        
        # Get examples from dataset
        examples = list(client.list_examples(dataset_id=dataset.id))
        
        # Create advanced evaluators
        evaluators = create_advanced_evaluators()
        
        # Simulate competing models
        runs = simulate_competing_models(examples)
        
        # Run advanced evaluations
        results = run_advanced_evaluations(dataset, evaluators, runs)
        
        # Display results
        display_advanced_results(results, runs)
        
        print("\n🎉 Advanced demo completed successfully!")
        print("\n💡 Advanced Features Demonstrated:")
        print("  • LLM-as-judge evaluation for quality assessment")
        print("  • Aspect coverage analysis for completeness")
        print("  • Pairwise model comparison")
        print("  • Regression testing between model versions")
        print("  • Sophisticated scoring and analysis")
        
    except Exception as e:
        print(f"❌ Error during advanced demo: {e}")
        print("This might be due to missing API keys or network issues.")

if __name__ == "__main__":
    main()

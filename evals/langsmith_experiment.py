#!/usr/bin/env python3
"""
LangSmith Experiment Runner - Following Official Quickstart

This script demonstrates how to run experiments in LangSmith following
the official evaluation quickstart from the LangSmith documentation.
"""

import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LangSmith components
from langsmith import Client, wrappers
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Set up clients
client = Client()

def create_dataset():
    """Create a dataset for the experiment following the quickstart pattern"""
    print("🔍 Looking for existing experiment dataset...")
    
    try:
        # Try to find existing dataset
        datasets = list(client.list_datasets())
        for dataset in datasets:
            if "langsmith-experiment-dataset" in dataset.name.lower():
                print(f"✅ Found existing dataset: {dataset.name}")
                return dataset
        
        # If not found, create a new one
        print("🚀 Creating new experiment dataset...")
        
        dataset = client.create_dataset(
            dataset_name="langsmith-experiment-dataset",
            description="Dataset for LangSmith experiment following the quickstart pattern"
        )
        
        # Create examples following the quickstart format
        examples = [
            {
                "inputs": {"question": "Explain the concept of machine learning in simple terms"},
                "outputs": {"answer": "Machine learning is a type of artificial intelligence where computers learn from examples to make predictions or decisions without being explicitly programmed for each task."},
            },
            {
                "inputs": {"question": "What are the benefits of using Python for data science?"},
                "outputs": {"answer": "Python offers excellent libraries like pandas, numpy, and scikit-learn, has readable syntax, strong community support, and integrates well with other tools in the data science ecosystem."},
            },
            {
                "inputs": {"question": "How does renewable energy help combat climate change?"},
                "outputs": {"answer": "Renewable energy reduces greenhouse gas emissions, decreases dependence on fossil fuels, provides sustainable power sources, and helps meet climate targets while creating green jobs."},
            }
        ]
        
        # Add examples to the dataset using the quickstart method
        client.create_examples(dataset_id=dataset.id, examples=examples)
        
        print(f"✅ Created new experiment dataset: {dataset.name}")
        return dataset
        
    except Exception as e:
        print(f"❌ Error with dataset: {e}")
        raise e

def correctness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict):
    """Evaluator following the quickstart pattern"""
    # Simple correctness check - compare key terms
    question = inputs["question"].lower()
    answer = outputs["answer"].lower()
    reference = reference_outputs["answer"].lower()
    
    # Extract key terms from question
    key_terms = [word for word in question.split() if len(word) > 4]
    
    # Check if answer contains key terms from question
    relevant_terms = [term for term in key_terms if term in answer]
    relevance_score = len(relevant_terms) / max(len(key_terms), 1)
    
    # Check if answer contains key terms from reference
    reference_terms = [word for word in reference.split() if len(word) > 4]
    accuracy_terms = [term for term in reference_terms if term in answer]
    accuracy_score = len(accuracy_terms) / max(len(reference_terms), 1)
    
    # Overall correctness score
    correctness_score = (relevance_score + accuracy_score) / 2
    
    return {
        "correctness": correctness_score,
        "relevance": relevance_score,
        "accuracy": accuracy_score,
        "comment": f"Relevance: {relevance_score:.3f}, Accuracy: {accuracy_score:.3f}"
    }

def target(inputs: dict) -> dict:
    """Target function following the quickstart pattern"""
    # Create the LLM chain
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the following question accurately and concisely:"),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    
    # Execute the chain
    response = chain.invoke({"question": inputs["question"]})
    
    return {"answer": response.content.strip()}

def run_experiment():
    """Run the experiment following the official quickstart pattern"""
    print("🧪 Running LangSmith experiment following official quickstart...")
    
    # Create/get dataset
    dataset = create_dataset()
    print(f"📊 Using dataset: {dataset.name}")
    
    # Run the evaluation using the official client.evaluate() method
    print("🚀 Starting evaluation...")
    
    experiment_results = client.evaluate(
        target,
        data=dataset.name,  # Use dataset name as specified in quickstart
        evaluators=[
            correctness_evaluator,
        ],
        experiment_prefix="langsmith-quickstart-demo",
        max_concurrency=1,  # Keep it simple for demo
    )
    
    print("✅ Evaluation completed!")
    print(f"🔗 Check your LangSmith dashboard for results!")
    
    return experiment_results

def main():
    """Main experiment function following the quickstart pattern"""
    print("🧪 LangSmith Experiment Runner - Official Quickstart")
    print("="*60)
    
    try:
        # Check environment variables
        if not os.getenv("LANGSMITH_API_KEY"):
            print("❌ LANGSMITH_API_KEY not set. Please set it to run experiments.")
            print("   Get it from: https://smith.langchain.com/settings")
            return
        
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ OPENAI_API_KEY not set. Required for LLM calls.")
            return
        
        # Check if tracing is enabled
        if not os.getenv("LANGSMITH_TRACING"):
            print("⚠️  LANGSMITH_TRACING not set. Set to 'true' for full tracing.")
        
        # Run the experiment
        results = run_experiment()
        
        print("\n🎉 Experiment completed successfully!")
        print("\n💡 Next Steps:")
        print("  • Check your LangSmith dashboard for detailed results")
        print("  • Explore the experiment in the Experiments tab")
        print("  • Compare different configurations")
        print("  • Use insights to optimize your prompts and models")
        
        print(f"\n🔗 LangSmith Dashboard: https://smith.langchain.com/")
        
    except Exception as e:
        print(f"❌ Error during experiment: {e}")
        print("This might be due to missing API keys or network issues.")

if __name__ == "__main__":
    main()

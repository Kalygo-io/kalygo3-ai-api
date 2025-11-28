#!/usr/bin/env python3
"""
Quick script to check if evaluation scores are stored in LangSmith

Usage:
    python evals/ai_school_agent/check_scores.py [experiment_name]
    python evals/ai_school_agent/check_scores.py ai-school-agent-qa-1e4f5e9b
"""
import os
import sys
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

client = Client(
    api_key=os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"),
    api_url=os.getenv("LANGSMITH_ENDPOINT")
)

# Get experiment name from command line or use default
if len(sys.argv) > 1:
    experiment_name = sys.argv[1]
else:
    # Default experiment name - update this or pass as argument
    experiment_name = "ai-school-agent-qa-4abae783"
    print("⚠️  No experiment name provided, using default.")
    print(f"   Usage: python {sys.argv[0]} <experiment_name>")
    print()

print(f"🔍 Checking scores for experiment: {experiment_name}")

try:
    # Get runs from the experiment (using project_name or experiment name)
    # Try both project_name and experiment name patterns
    runs = []
    try:
        runs = list(client.list_runs(project_name=experiment_name, limit=20))
    except Exception:
        # Try as experiment name instead
        try:
            # List all projects and find matching one
            projects = list(client.list_projects())
            matching_projects = [p for p in projects if experiment_name in p.name]
            if matching_projects:
                print(f"📋 Found matching project: {matching_projects[0].name}")
                runs = list(client.list_runs(project_name=matching_projects[0].name, limit=20))
        except Exception as e:
            print(f"⚠️  Error listing runs: {e}")
    
    # Also try to find evaluator runs directly
    print(f"\n🔍 Also searching for evaluator runs...")
    try:
        all_runs = list(client.list_runs(project_name=experiment_name, run_type="evaluator", limit=20))
        if all_runs:
            print(f"✅ Found {len(all_runs)} evaluator runs directly!")
            evaluator_feedback_count = 0
            for eval_run in all_runs[:5]:
                feedback = list(client.list_feedback(run_ids=[eval_run.id]))
                if feedback:
                    evaluator_feedback_count += len(feedback)
                    print(f"   ✅ Evaluator '{eval_run.name}': {len(feedback)} feedback entries")
                    for fb in feedback:
                        score_str = f"{fb.score:.3f}" if fb.score is not None else "N/A"
                        print(f"      - {fb.key}: {score_str}")
            if evaluator_feedback_count > 0:
                print(f"\n🎉 Found {evaluator_feedback_count} total evaluator feedback entries!")
    except Exception as e:
        print(f"⚠️  Error searching for evaluator runs: {e}")
    
    if not runs:
        print("❌ No runs found. Check the experiment name.")
        print("\n💡 Tip: Use the experiment name from LangSmith dashboard")
        print("   Example: ai-school-agent-qa-4abae783")
    else:
        print(f"✅ Found {len(runs)} runs")
        
        # Check all runs for feedback
        total_feedback = 0
        for i, run in enumerate(runs[:5], 1):  # Check first 5 runs
            print(f"\n📊 Run {i}:")
            print(f"   ID: {run.id}")
            print(f"   Run Type: {run.run_type}")
            print(f"   Name: {run.name}")
            
            # Check inputs structure (handle nested structure)
            if run.inputs:
                print(f"   Inputs keys: {list(run.inputs.keys())}")
                # Handle nested inputs structure
                if isinstance(run.inputs, dict) and 'inputs' in run.inputs:
                    nested_inputs = run.inputs['inputs']
                    question = nested_inputs.get("question", nested_inputs.get("q", "N/A"))
                else:
                    question = run.inputs.get("question", run.inputs.get("q", "N/A"))
                print(f"   Question: {str(question)[:60]}...")
            else:
                print(f"   ⚠️  No inputs found")
            
            # Check outputs structure
            if run.outputs:
                if isinstance(run.outputs, dict):
                    print(f"   Outputs keys: {list(run.outputs.keys())}")
                    if 'output' in run.outputs:
                        output_preview = str(run.outputs['output'])[:60]
                        print(f"   Output preview: {output_preview}...")
                else:
                    print(f"   Outputs: {str(run.outputs)[:60]}...")
            
            # Check for child runs using trace_id instead
            try:
                # Get the trace to find child runs
                if hasattr(run, 'trace_id') and run.trace_id:
                    trace_runs = list(client.list_runs(trace_id=run.trace_id, limit=50))
                    # Filter for evaluator runs
                    evaluator_runs = [r for r in trace_runs if r.run_type == 'evaluator' or 'evaluator' in r.name.lower()]
                    if evaluator_runs:
                        print(f"   🔍 Found {len(evaluator_runs)} evaluator runs in trace")
                        for eval_run in evaluator_runs[:3]:
                            print(f"      - Evaluator: {eval_run.name} ({eval_run.run_type})")
                            eval_feedback = list(client.list_feedback(run_ids=[eval_run.id]))
                            if eval_feedback:
                                print(f"        ✅ Has {len(eval_feedback)} feedback entries")
                                for fb in eval_feedback:
                                    score_str = f"{fb.score:.3f}" if fb.score is not None else "N/A"
                                    print(f"           Key: {fb.key}, Score: {score_str}")
            except Exception as e:
                print(f"   ⚠️  Error checking trace/evaluator runs: {e}")
            
            # Also check if this run itself has a trace_id we can use
            if hasattr(run, 'trace_id') and run.trace_id:
                print(f"   Trace ID: {run.trace_id}")
            
            # Try to get feedback directly
            try:
                feedback = list(client.list_feedback(run_ids=[run.id]))
                if feedback:
                    total_feedback += len(feedback)
                    print(f"   ✅ Found {len(feedback)} feedback entries:")
                    for fb in feedback:
                        score_str = f"{fb.score:.3f}" if fb.score is not None else "N/A"
                        comment_preview = fb.comment[:50] if fb.comment else "None"
                        print(f"      - Key: {fb.key}, Score: {score_str}, Comment: {comment_preview}...")
                else:
                    print(f"   ❌ No feedback found for this run")
            except Exception as e:
                print(f"   ⚠️  Error checking feedback: {e}")
        
        print(f"\n📈 Summary:")
        print(f"   Total runs checked: {min(len(runs), 5)}")
        print(f"   Total feedback entries: {total_feedback}")
        if total_feedback == 0:
            print(f"\n⚠️  No scores found! The evaluators may not have run successfully.")
            print(f"   Make sure you ran the evaluation with both evaluators enabled.")
                
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


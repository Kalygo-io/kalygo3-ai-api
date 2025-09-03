#!/usr/bin/env python3
"""
Demo Runner Script for LangSmith Evaluation Presentation

This script provides an easy way to run different evaluation demos
during your presentation. Perfect for live demonstrations!
"""

import sys
import os
from pathlib import Path

def print_banner():
    """Print a nice banner for the demo"""
    print("=" * 80)
    print("🎯 LangSmith Evaluation Demo Suite")
    print("=" * 80)
    print("Choose your demo:")
    print()

def print_menu():
    """Display the demo menu"""
    print("1. 🚀 Quick Start Demo (Basic - 5-7 min)")
    print("   Perfect for first-time audiences")
    print("   Shows: Dataset creation, custom evaluators, basic results")
    print()
    
    print("2. 🔬 Advanced Demo (Technical - 5-7 min)")
    print("   For audiences ready for sophisticated features")
    print("   Shows: LLM-as-judge, pairwise comparison, regression testing")
    print()
    
    print("3. 📚 Show Documentation")
    print("   Display key concepts and resources")
    print()
    
    print("4. 🧪 Test Setup")
    print("   Verify your environment is ready")
    print()
    
    print("5. 🚪 Exit")
    print()

def run_quick_start():
    """Run the quick start demo"""
    print("\n🚀 Starting Quick Start Demo...")
    print("This demo will take about 5-7 minutes.")
    print("Press Enter to continue...")
    input()
    
    try:
        # Import and run the quick start demo
        from quick_start_eval import main
        main()
    except ImportError as e:
        print(f"❌ Error importing quick start demo: {e}")
        print("Make sure quick_start_eval.py is in the same directory.")
    except Exception as e:
        print(f"❌ Error running demo: {e}")

def run_advanced():
    """Run the advanced demo"""
    print("\n🔬 Starting Advanced Demo...")
    print("This demo will take about 5-7 minutes.")
    print("Note: Requires OPENAI_API_KEY for LLM-as-judge evaluations.")
    print("Press Enter to continue...")
    input()
    
    try:
        # Import and run the advanced demo
        from advanced_eval_demo import main
        main()
    except ImportError as e:
        print(f"❌ Error importing advanced demo: {e}")
        print("Make sure advanced_eval_demo.py is in the same directory.")
    except Exception as e:
        print(f"❌ Error running demo: {e}")

def show_documentation():
    """Show key documentation and concepts"""
    print("\n📚 LangSmith Evaluation Key Concepts")
    print("=" * 50)
    
    concepts = [
        ("Datasets", "Collections of test inputs and reference outputs for evaluation"),
        ("Evaluators", "Functions that score how well your application performs"),
        ("LLM-as-Judge", "Using AI to evaluate AI responses for quality assessment"),
        ("Pairwise Evaluation", "Comparing outputs of two versions to determine which is better"),
        ("Regression Testing", "Ensuring new versions don't break existing functionality"),
        ("Aspect Coverage", "Measuring how well responses cover expected topics")
    ]
    
    for concept, description in concepts:
        print(f"\n🔹 {concept}")
        print(f"   {description}")
    
    print("\n💡 Key Benefits:")
    print("   • Systematic, repeatable evaluation")
    print("   • Quantitative quality metrics")
    print("   • Continuous improvement tracking")
    print("   • Production-ready evaluation framework")

def test_setup():
    """Test if the environment is properly set up"""
    print("\n🧪 Testing Your Setup...")
    print("=" * 40)
    
    # Check Python version
    print(f"✅ Python version: {sys.version.split()[0]}")
    
    # Check required packages
    required_packages = [
        "langsmith",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "dotenv"
    ]
    
    print("\n📦 Checking required packages:")
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - NOT FOUND")
    
    # Check environment variables
    print("\n🔑 Checking environment variables:")
    env_vars = {
        "LANGCHAIN_API_KEY": "LangSmith API key (optional but recommended)",
        "OPENAI_API_KEY": "OpenAI API key (required for advanced demo)"
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value[:10]}... (set)")
        else:
            print(f"   ⚠️  {var}: Not set - {description}")
    
    print("\n📝 Setup Notes:")
    print("   • Basic demo works without API keys (simulated data)")
    print("   • Advanced demo requires OPENAI_API_KEY for LLM-as-judge")
    print("   • LANGCHAIN_API_KEY enables full LangSmith integration")

def main():
    """Main demo runner"""
    while True:
        print_banner()
        print_menu()
        
        try:
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == "1":
                run_quick_start()
            elif choice == "2":
                run_advanced()
            elif choice == "3":
                show_documentation()
            elif choice == "4":
                test_setup()
            elif choice == "5":
                print("\n👋 Thanks for using the LangSmith Evaluation Demo Suite!")
                print("Good luck with your presentation! 🎉")
                break
            else:
                print("\n❌ Invalid choice. Please enter 1-5.")
            
            if choice in ["1", "2", "3", "4"]:
                print("\n" + "="*80)
                print("Press Enter to return to main menu...")
                input()
                
        except KeyboardInterrupt:
            print("\n\n👋 Demo interrupted. Thanks for using the demo suite!")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("Press Enter to continue...")
            input()

if __name__ == "__main__":
    main()

# LangSmith Evaluation Demo Suite

This folder contains comprehensive demonstrations of LangSmith's powerful evaluation framework, perfect for showcasing to audiences of 20-30 people.

## 🎯 What This Demo Shows

The evaluation scripts demonstrate the full power of LangSmith's evaluation capabilities:

### Core Concepts
- **Dataset Creation**: Building test datasets with examples and metadata
- **Custom Evaluators**: Creating rule-based and LLM-powered evaluators
- **Evaluation Execution**: Running evaluations on model outputs
- **Result Analysis**: Interpreting and comparing evaluation results

### Advanced Features
- **LLM-as-Judge**: Using AI to evaluate AI responses
- **Pairwise Comparisons**: Comparing different model versions
- **Regression Testing**: Measuring improvements over time
- **Aspect Coverage**: Ensuring responses cover expected topics

## 📁 Files

### `quick_start_eval.py`
**Perfect for beginners and first-time audiences**

- Creates a simple Q&A dataset with 5 examples
- Implements 3 custom evaluators:
  - Answer Length Evaluator (rule-based)
  - Answer Relevance Evaluator (keyword-based)
  - Category Accuracy Evaluator (metadata-based)
- Simulates LLM responses
- Runs evaluations and displays results

**Key Features:**
- Easy to understand and follow
- Demonstrates basic evaluation concepts
- Works without external API keys (simulated data)
- Clear output formatting

### `advanced_eval_demo.py`
**For audiences ready for sophisticated features**

- Creates advanced datasets with expected aspects
- Implements LLM-as-judge evaluators
- Performs pairwise model comparisons
- Shows regression testing between model versions
- Provides detailed improvement analysis

**Key Features:**
- LLM-powered quality assessment
- Model version comparison
- Sophisticated scoring algorithms
- Professional-grade evaluation patterns

## 🚀 Quick Start

### Prerequisites
1. **Environment Variables** (optional but recommended):
   ```bash
   export LANGCHAIN_API_KEY="your_langsmith_api_key"
   export OPENAI_API_KEY="your_openai_api_key"  # For advanced demo
   ```

2. **Dependencies**: All required packages are already in the main project's `requirements.txt`

### Running the Demos

#### Basic Demo (Recommended for first-time audiences)
```bash
cd evals
python quick_start_eval.py
```

#### Advanced Demo (For technical audiences)
```bash
cd evals
python advanced_eval_demo.py
```

## 🎭 Demo Script for Presenters

### Opening (2 minutes)
"Today I'm going to show you how LangSmith's evaluation framework can transform how you test and improve your AI applications. We'll go from basic evaluations to sophisticated model comparisons."

### Basic Demo (5-7 minutes)
1. **Run the script**: `python quick_start_eval.py`
2. **Explain what's happening**:
   - "First, we're creating a dataset of test questions and expected answers"
   - "Then we'll create custom evaluators that measure different aspects of quality"
   - "Finally, we'll run these evaluations and see the results"

3. **Key talking points**:
   - "Notice how we can define custom metrics that matter for your use case"
   - "The evaluators run automatically and give us quantitative scores"
   - "This replaces manual testing with systematic, repeatable evaluation"

### Advanced Demo (5-7 minutes)
1. **Run the script**: `python advanced_eval_demo.py`
2. **Explain the advanced features**:
   - "Now we're using AI to evaluate AI - the LLM-as-judge approach"
   - "We can compare different model versions to see improvements"
   - "This enables continuous improvement and regression testing"

3. **Key talking points**:
   - "This is how you can systematically improve your AI applications"
   - "Notice the detailed analysis showing exactly where improvements occurred"
   - "This framework scales to production applications with thousands of examples"

### Closing (2 minutes)
"LangSmith's evaluation framework gives you the tools to build better AI applications systematically. Instead of guessing what works, you can measure it, improve it, and track progress over time."

## 🔧 Customization for Your Demo

### Modify the Dataset
Edit the examples in either script to match your audience's interests:
- **Technical audience**: Programming, AI, engineering questions
- **Business audience**: Customer service, marketing, analysis questions
- **General audience**: Current events, trivia, practical knowledge

### Adjust Evaluation Criteria
Modify the evaluators to focus on aspects relevant to your use case:
- **Accuracy**: Factual correctness
- **Clarity**: Readability and understanding
- **Completeness**: Coverage of expected topics
- **Helpfulness**: Practical value to users

### Add Your Own Evaluators
Create custom evaluators that measure what matters for your application:
- **Domain-specific metrics**: Industry-specific quality measures
- **User satisfaction proxies**: Metrics that correlate with user happiness
- **Business impact measures**: ROI, conversion rates, etc.

## 🎯 Audience Engagement Tips

### Interactive Elements
1. **Ask for questions**: "What aspects would you want to evaluate in your AI application?"
2. **Show real-time results**: Run the script during the presentation
3. **Compare scenarios**: "What if we changed the evaluation criteria?"

### Common Questions & Answers
- **"How much does this cost?"**: "LangSmith has a generous free tier, and evaluations scale with your usage"
- **"How accurate are the evaluations?"**: "You can combine automated and human evaluation for the best results"
- **"Can this work with any AI model?"**: "Yes, it's model-agnostic and works with any LLM or AI system"

### Technical Deep-Dives (if time permits)
- Show the evaluator code structure
- Explain how to integrate with existing CI/CD pipelines
- Demonstrate dataset versioning and management

## 🚨 Troubleshooting

### Common Issues
1. **API Key Errors**: Check environment variables are set correctly
2. **Import Errors**: Ensure all dependencies are installed
3. **Network Issues**: Verify internet connectivity for API calls

### Fallback Options
- **No API Keys**: The basic demo works with simulated data
- **Network Issues**: Show the code structure and explain what it would do
- **Time Constraints**: Focus on the basic demo and skip advanced features

## 📚 Additional Resources

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [Evaluation Concepts](https://docs.smith.langchain.com/evaluation?mode=sdk)
- [LangSmith Academy](https://academy.langchain.com/)
- [Community Forum](https://github.com/langchain-ai/langchain/discussions)

---

**Happy Evaluating! 🎉**

This demo suite is designed to showcase the power and flexibility of LangSmith's evaluation framework. Feel free to customize it for your specific audience and use case.

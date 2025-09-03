# tools/calculator_tool.py
from __future__ import annotations
from typing import Optional, Union
import math

from langchain.tools.base import StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field


class CalculatorArgs(BaseModel):
    expression: str = Field(..., description="Mathematical expression to evaluate (e.g., '2 + 3', 'sin(45)', 'sqrt(16)')")
    operation_type: Optional[str] = Field(None, description="Type of operation: 'basic' (+, -, *, /, ^), 'trig' (sin, cos, tan), 'advanced' (sqrt, log, exp), or 'auto' to detect automatically")


def safe_eval(expression: str) -> Union[float, int, str]:
    """
    Safely evaluate mathematical expressions with basic operations.
    Supports: +, -, *, /, ^, sin, cos, tan, sqrt, log, exp, pi, e
    """
    # Clean the expression
    expr = expression.lower().replace(' ', '').replace('×', '*').replace('÷', '/')
    
    # Handle common mathematical constants
    expr = expr.replace('pi', str(math.pi)).replace('e', str(math.e))
    
    # Handle trigonometric functions (convert degrees to radians)
    if 'sin(' in expr or 'cos(' in expr or 'tan(' in expr:
        # Extract angle values and convert to radians
        import re
        for func in ['sin', 'cos', 'tan']:
            pattern = rf'{func}\(([^)]+)\)'
            matches = re.findall(pattern, expr)
            for match in matches:
                try:
                    angle = float(match)
                    angle_rad = math.radians(angle)
                    expr = expr.replace(f'{func}({match})', f'{func}({angle_rad})')
                except ValueError:
                    pass
    
    # Handle power operations
    expr = expr.replace('^', '**')
    
    # Handle square root
    if 'sqrt(' in expr:
        expr = expr.replace('sqrt', 'math.sqrt')
    
    # Handle natural logarithm
    if 'ln(' in expr:
        expr = expr.replace('ln', 'math.log')
    
    # Handle common logarithm (base 10)
    if 'log(' in expr:
        expr = expr.replace('log', 'math.log10')
    
    # Handle exponential
    if 'exp(' in expr:
        expr = expr.replace('exp', 'math.exp')
    
    # Define allowed names for security
    allowed_names = {
        'math': math,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'sqrt': math.sqrt,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'abs': abs,
        'round': round,
        'floor': math.floor,
        'ceil': math.ceil,
        'pi': math.pi,
        'e': math.e
    }
    
    try:
        # Use eval with restricted globals for security
        result = eval(expr, {"__builtins__": {}}, allowed_names)
        
        # Handle division by zero
        if isinstance(result, (int, float)) and math.isnan(result):
            return "Error: Invalid mathematical operation (NaN)"
        if isinstance(result, (int, float)) and math.isinf(result):
            return "Error: Result is infinite"
        
        # Return integer if result is whole number, otherwise float
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result
        
    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        return f"Error: Could not evaluate expression - {str(e)}"


async def calculator_impl(expression: str, operation_type: Optional[str] = None) -> str:
    """
    Evaluate mathematical expressions with comprehensive error handling.
    Supports basic arithmetic, trigonometry, logarithms, and more.
    """
    try:
        result = safe_eval(expression)
        
        if isinstance(result, str) and result.startswith("Error:"):
            return result
        
        # Format the result nicely
        if isinstance(result, (int, float)):
            if isinstance(result, float):
                # Limit decimal places for readability
                if abs(result) < 1e-10:
                    result = 0.0
                elif abs(result) < 1e-6 or abs(result) > 1e6:
                    result = f"{result:.2e}"
                else:
                    result = round(result, 6)
            
            return f"Result: {result}"
        else:
            return f"Result: {result}"
            
    except Exception as e:
        return f"Error: Unexpected error occurred - {str(e)}"


calculator_tool = StructuredTool(
    name="calculator",
    description="A comprehensive calculator that can handle basic arithmetic (+, -, *, /, ^), trigonometry (sin, cos, tan), square roots (sqrt), logarithms (log, ln), exponentials (exp), and more. Input mathematical expressions like '2 + 3', 'sin(45)', 'sqrt(16)', 'log(100)', etc.",
    args_schema=CalculatorArgs,
    func=calculator_impl,
    coroutine=calculator_impl,
)

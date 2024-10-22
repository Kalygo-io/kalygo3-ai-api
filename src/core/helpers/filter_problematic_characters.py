import re

def filter_problematic_characters(text: str) -> str:
    """
    Detect and remove problematic characters from the input text.

    Args:
        text (str): Input text to sanitize.
    
    Returns:
        str: Sanitized text with problematic characters removed.
    """
    # List of zero-width characters
    zero_width_chars = [
        "\u200B",  # Zero Width Space
        "\u200C",  # Zero Width Non-Joiner
        "\u200D",  # Zero Width Joiner
        "\uFEFF",  # Zero Width No-Break Space
    ]

    # List of bidirectional override characters
    bidi_override_chars = [
        "\u202A",  # Left-to-Right Embedding
        "\u202B",  # Right-to-Left Embedding
        "\u202C",  # Pop Directional Formatting
        "\u202D",  # Left-to-Right Override
        "\u202E",  # Right-to-Left Override
    ]

    # Combine all problematic characters into a single regex pattern
    problematic_chars = zero_width_chars + bidi_override_chars
    regex_pattern = f"[{''.join(problematic_chars)}]"

    # Remove problematic characters from the text
    sanitized_text = re.sub(regex_pattern, "", text)

    return sanitized_text
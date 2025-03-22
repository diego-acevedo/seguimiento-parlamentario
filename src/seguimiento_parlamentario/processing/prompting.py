from abc import ABC, abstractmethod
from openai import OpenAI
import os


class PromptModel(ABC):
    """
    Abstract base class for AI-powered text processing using large language models.

    This class provides a standardized interface for interacting with language models
    through the OpenRouter API, handling authentication, request formatting, and
    response processing. Subclasses must implement specific prompt building logic
    for their particular use cases.
    """

    def __init__(self, base_system_message):
        """
        Initialize the prompt model with a system message.

        The system message defines the AI assistant's role, expertise, and behavior
        for all interactions using this model instance.

        Args:
            base_system_message: String containing the system prompt that defines
                               the AI assistant's role and instructions
        """
        self.base_system_message = base_system_message

    def process(self, data):
        """
        Process input data through the configured language model.

        Creates a chat completion request using the system message and a dynamically
        built prompt, then returns the AI-generated response. The method handles
        API authentication and request formatting automatically.

        Args:
            data: Input data to be processed (format depends on subclass implementation)

        Returns:
            String containing the AI-generated response

        Environment Variables Required:
            OPENROUTER_API_KEY: API key for OpenRouter service
            MODEL_NAME: Name of the language model to use
        """
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        response = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=[
                {"role": "system", "content": self.base_system_message},
                {"role": "user", "content": self.build_prompt(data)},
            ],
        )
        result = response.choices[0].message.content

        return result

    @abstractmethod
    def build_prompt(self, data):
        """
        Build the user prompt from input data.

        This method must be implemented by subclasses to define how input data
        is transformed into a specific prompt for the language model. The prompt
        should be tailored to the particular use case and desired output format.

        Args:
            data: Input data to be transformed into a prompt

        Returns:
            String containing the formatted prompt for the AI model
        """
        ...

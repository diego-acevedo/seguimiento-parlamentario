from abc import ABC, abstractmethod
from openai import OpenAI
import os

class PromptModel(ABC):
  
  def __init__(self, base_system_message):
    self.base_system_message = base_system_message

  def process(self, data):
    client = OpenAI(
      base_url="https://openrouter.ai/api/v1",
      api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    response = client.chat.completions.create(
      model=os.getenv("MODEL_NAME"),
      messages=[
        {
          "role": "system",
          "content": self.base_system_message
        },
        {
          "role": "user",
          "content": self.build_prompt(data)
        }
      ]
    )
    result = response.choices[0].message.content

    return result

  @abstractmethod
  def build_prompt(self, data):
    ...
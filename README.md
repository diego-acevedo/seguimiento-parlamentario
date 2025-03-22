# Seguimiento Parlamentario

A tool for automatic processing of Chilean Congress sessions.

---

## Table of Contents
- [About](#about)  
- [Features](#features)  
- [Installation](#installation)  
- [Usage](#usage)  
- [Configuration](#configuration)
- [Contributing](#contributing)  
- [License](#license)

---

## About
This project addresses the need to automate the monitoring of legislative activity in Chile. To improve access to legislative information and reduce reliance on manual processes, this project proposes a solution that integrates the extraction and processing of parliamentary data to generate structured reports on Congressional sessions.  

The proposed system performs periodic data extraction using web scraping techniques on legislative websites and automatic transcription of session videos. This information is then processed using language models (LLMs) to produce structured reports highlighting relevant details. Additionally, Retrieval-Augmented Generation (RAG) techniques are employed to handle thematic queries and retrieve information from multiple sessions, improving topic coverage. The post-processed data can be accessed through a web API.

---

## Features
- **Web scraping for automatic extraction:** Periodically collects legislative documents and session information from official Chilean parliamentary websites.  
- **Automatic transcription of videos:** Converts parliamentary session videos into text for further processing and analysis.  
- **Processing and summarization with LLMs:** Uses language models to generate structured, detailed reports highlighting key legislative information.  
- **Question-Answering with RAG:** Enables thematic queries and retrieves relevant information from multiple sessions using Retrieval-Augmented Generation techniques.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/diego-acevedo/seguimiento-parlamentario.git

# Change directory
cd seguimiento-parlamentario

# Install dependencies
pip install -e .
```

## Usage

You can run the web API to automatically process the data and access the results running the following commands

```bash
# To run using Celery
make run

# To run with GCP
make gcloud-deploy
```

## Configuration

Fill out the [env template file](.env.template) and rename it to `.env`

```
# Setting mode (celery or gcloud)
SERVICE_MODE=...

# If using Google Cloud
PROJECT_ID=... # Google Cloud project ID
FIRESTORE_ID=... # Firestore ID

# If using Celery
MONGO_URL=... # URL to MongoDB database
AMQP_URL=... # URL to RabbitMQ queue

# Global variables
APP_URL=... # URL of the app (localhost)
PORT=... # Port where to run the app
MODEL_NAME=... # Name of the LLM model use for processing (OpenRouter)
OPENROUTER_API_KEY=... # OpenRouter API key
OPENAI_API_KEY=... # OpenAI API key
PINECONE_API_KEY=... # Pinecone API key
PINECONE_INDEX_HOST=... # Pinecone index where to store the data
```

## Contributing

If you want to contribute to this project, follow these steps:

1. Fork the repository
2. Create a new branch (git checkout -b feature-name)
3. Make your changes
4. Commit (git commit -m "Add feature")
5. Push (git push origin feature-name)
6. Open a Pull Request

## License

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
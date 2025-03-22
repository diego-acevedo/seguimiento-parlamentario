from seguimiento_parlamentario.processing.prompting import PromptModel
from seguimiento_parlamentario.core.db import PineconeDatabase


class QuestionAnswerModel(PromptModel):
    """
    Specialized prompt model for answering questions about parliamentary activities.

    This class implements a retrieval-augmented generation (RAG) system that combines
    semantic search capabilities with large language model processing to provide
    accurate, cited responses about Chilean parliamentary sessions and activities.
    """

    def __init__(self):
        """
        Initialize the question answering model with parliamentary expertise.

        Sets up the system message that defines the AI assistant's role as
        an expert chatbot specializing in Chilean parliamentary topics.
        """
        base_system_message = "Eres un chatbot experto en temas parlamentarios que responde preguntas sobre las actividades legislativas del Congreso de Chile."
        super().__init__(base_system_message)

    def build_prompt(self, data):
        """
        Construct the complete prompt for question answering with context.

        Builds a prompt that includes relevant document fragments from parliamentary
        transcriptions along with specific instructions for citing sources and
        handling insufficient information scenarios.

        Args:
            data: Dictionary containing the user message and relevant document chunks

        Returns:
            String containing the complete prompt for AI processing
        """
        message = data["message"]
        chunks = data["chunks"]

        prompt = f"""
A continuación se te proporcionan fragmentos de transcripciones del Congreso de Chile. Utiliza únicamente esta información para responder a la pregunta del usuario.

Utiliza la numeración de los fragmentos para citar el contenido, usando el mismo formato de numeración con corchetes ([1], [2], [3], etc).

Si la información proporcionada no es suficiente para dar una respuesta precisa, responde con "No tengo suficiente información para responder con certeza".

### Fragmentos del Congreso:
{self.build_chunks(chunks)}

### Pregunta del usuario:
{message}

### Respuesta:
"""
        return prompt

    def build_chunks(self, chunks):
        """
        Format document chunks into a numbered list for the prompt.

        Converts the chunks dictionary into a formatted string where each
        session's content is numbered sequentially for easy citation reference.

        Args:
            chunks: Dictionary mapping session IDs to lists of text chunks

        Returns:
            String containing numbered and formatted document chunks
        """
        formatted_chunks = [
            f"[{i}] {' '.join(chunk)}"
            for i, (_, chunk) in enumerate(chunks.items(), start=1)
        ]

        return "\n".join(formatted_chunks)

    def format_chunks(self, chunks):
        """
        Organize retrieved chunks by session ID and create citation mapping.

        Groups chunks from the vector database results by their session ID
        and creates a citation mapping that links bracket numbers to session IDs
        for proper source attribution.

        Args:
            chunks: List of chunk objects from vector database query results

        Returns:
            Tuple containing:
                - Dictionary mapping session IDs to lists of chunk texts
                - Dictionary mapping citation numbers to session IDs
        """
        chunks_by_session = {}

        for chunk in chunks:
            if not chunks_by_session.get(chunk["fields"]["session_id"]):
                chunks_by_session[str(chunk["fields"]["session_id"])] = []
            chunks_by_session[str(chunk["fields"]["session_id"])].append(
                chunk["fields"]["chunk_text"]
            )

        citation = {
            f"[{i}]": int(float(session_id))
            for i, session_id in enumerate(chunks_by_session.keys(), start=1)
        }

        return chunks_by_session, citation

    def ask(self, question, filters={}):
        """
        Process a user question and return an AI-generated answer with citations.

        This method orchestrates the complete question-answering pipeline:
        retrieving relevant chunks from the vector database, formatting them,
        processing through the language model, and returning both the response
        and citation mapping.

        Args:
            question: User's question about parliamentary activities
            filters: Optional dictionary of filters for database query (e.g., date range, chamber)

        Returns:
            Tuple containing:
                - String with the AI-generated response
                - Dictionary mapping citation brackets to session IDs
        """
        db = PineconeDatabase()

        chunks = db.retrieve_records(question, filters=filters)
        chunks_by_session, citation = self.format_chunks(chunks)

        data = {"message": question, "chunks": chunks_by_session}

        response = self.process(data)

        return response, citation

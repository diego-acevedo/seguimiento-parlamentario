from abc import ABC, abstractmethod
from seguimiento_parlamentario.processing.prompting import PromptModel
from babel.dates import format_datetime


class Summarizer(PromptModel, ABC):
    """
    Abstract base class for generating comprehensive reports from parliamentary session data.

    This class extends PromptModel to provide AI-powered legislative analysis capabilities
    that transform session transcripts into structured markdown reports covering all
    key aspects of parliamentary discussions, agreements, and participants.
    """

    def __init__(self):
        """
        Initialize the summarizer with legislative analysis expertise.

        Sets up the base system message that defines the AI assistant's role as
        an expert in legislative analysis specializing in Chilean parliamentary sessions.
        """
        base_system_message = "Eres un modelo experto en análisis legislativo. Tu tarea es leer y generar un reporte a partir de las transcripciones de sesiones del Congreso de Chile."
        super().__init__(base_system_message)

    def build_prompt(self, data):
        """
        Construct the complete prompt for comprehensive session report generation.

        Builds a detailed prompt that includes session metadata, context, attendance,
        and transcription, along with specific instructions for creating structured
        markdown reports with multiple analysis sections including headlines, keywords,
        bill discussions, participants, agreements, disagreements, and actionable insights.

        Args:
            data: Dictionary containing session and commission information

        Returns:
            String containing the complete prompt for AI processing
        """
        session = data["session"]
        commission = data["commission"]

        prompt = f"""
Genera un informe de la siguiente transcripción de una sesión de la {commission['name']} en {commission['chamber']} de Chile, realizada el día {format_datetime(session['start'], "EEEE d 'de' MMMM 'de' y", locale='es')}. El resumen debe estar organizado en las siguientes secciones:

# **Titular**: Crea un titular representativo de lo discutido en la sesión. Debe describir los temas tratados en la sesión.
## **Palabras claves**: Enumera las cinco palabras claves que mejor describan el contenido de la sesión. Deben ser relevantes y específicas a los problemas tratados en la sesión. Descarta palabras que puedan ser muy generales y que apliquen a la mayoría de las sesiones, como 'Legislación' o 'Congreso'.
## **Proyectos de ley**: Enumera los proyectos de ley y boletines discutidos en la sesión, junto con una breve descripción de lo que tratan.
## **Participantes**: Enumera los participantes de la sesión en las siguientes categorías:
### Parlamentarios principales: Enumera los parlamentarios que fueron más relevantes para la discusión.
### Invitados a la comisión: Enumera los invitados que participaron activamente en la sesión, exponiendo sobre algún tema relevante.
### Otros actores presentes: Esta sección es opcional, y solo debe ser incluída si algún participante relevante no pertenece a las categorías anteriores.
## **Temas principales tratados**: Enumera los temas más importantes discutidos durante la sesión, en formato de lista clara.
## **Resumen de la sesión**: Redacta un texto en formato de noticia que informe sobre todos los puntos abordados en la sesión. Debe responder el 'Qué', 'Quién', 'Como', 'Donde', 'Cuando' y 'Por qué'. Se debe mencionar quienes intervinieron, cuales fueron sus intervenciones, y cual fue el descenlace de la discusión. Este texto debe tener una extensión de 500 palabras aproximadamente.
## **Puntos de acuerdo**: Describe los puntos o temas en los que hubo consenso entre los participantes. Incluye los argumentos más relevantes que se entregaron a favor y explica por qué se logró el acuerdo, y quienes intervinieron.
## **Puntos de desacuerdo**: Describe los puntos o temas que generaron discusión o desacuerdo. Explica las posturas contrapuestas, incluyendo los argumentos clave entregados por las distintas partes, quienes dieron estos argumentos, y por qué no se logró llegar a un consenso. No incluyas tensiones producidas entre parlamentarios, sino que solo enfocate en las decisiones legislativas.
## **Principales entidades nombradas**: Enumera personas, instituciones, eventos o lugares que fueron mencionadas en la sesión, y cual es su importancia para esta. Ignora entidades que sean muy generales y puedan aplicar a las demás sesiones, como 'Congreso', 'Gobierno de Chile' o los mismos parlamentarios.
## **Insights accionables**: Enumera posibles insights accionables que puedan ser de ínteres para organizaciones dependientes de la legislación discutida (ej. que suscite decisiones, permita anticipar escenarios normativos, o guiar hacia objetivos de lobby).

Instrucciones adicionales:
- La respuesta debe estar estructurada en formato Markdown. Usa el titular generado como título principal (#), y el resto de secciones como subtítulos (##).
- Usa tanto el contexto como la transcripción completa para elaborar un resumen lo más completo posible.
- No te limites al contexto ni a la lista de participantes: es importante incluir las cosas que aparecen en la transcripción que fueron omitidas en el contexto.

### Contexto:
{self.get_context(session)}

### Participantes:
{self.get_attendance(session)}

### Transcripción:
{session['transcript']}
"""
        return prompt

    @abstractmethod
    def get_context(self, session):
        """
        Extract and format contextual information from session data.

        This method must be implemented by subclasses to handle the specific
        context data structure for each parliamentary chamber.

        Args:
            session: Dictionary containing session data

        Returns:
            String containing formatted context information
        """
        ...

    @abstractmethod
    def get_attendance(self, session):
        """
        Extract and format attendance information from session data.

        This method must be implemented by subclasses to handle the specific
        attendance data structure for each parliamentary chamber.

        Args:
            session: Dictionary containing session data

        Returns:
            String containing formatted attendance information
        """
        ...


class SenateSummarizer(Summarizer):
    """
    Specialized summarizer for Senate session reports.

    This class implements the abstract methods to handle the Senate's specific
    data format for context (topics, aspects, agreements) and attendance
    (members and guests) in comprehensive legislative analysis reports.
    """

    def get_context(self, session):
        """
        Format Senate session context information for report generation.

        Extracts and formats topics, aspects considered, and agreements
        from Senate session context data into a structured format.

        Args:
            session: Dictionary containing Senate session data

        Returns:
            String containing formatted Senate context information
        """
        contexts = []
        for ctx in session["context"]:
            contexts.append(
                f"- Tema: {ctx.get('topic')}\n- Aspectos: {ctx.get('aspects')}\n- Acuerdos: {ctx.get('agreements')}"
            )
        return "\n".join(contexts)

    def get_attendance(self, session):
        """
        Format Senate session attendance information for report generation.

        Extracts and formats member and guest attendance data from
        Senate session attendance records into a structured format.

        Args:
            session: Dictionary containing Senate session data

        Returns:
            String containing formatted Senate attendance information
        """
        members = []
        guests = []
        for att in session["attendance"].get("members"):
            members.append(f"- Nombre: {att}")
        for att in session["attendance"].get("guests"):
            guests.append(f"- {att}")
        attendees = ["Miembros:", "\n".join(members), "Invitados:", "\n".join(guests)]
        return "\n".join(attendees)


class ChamberOfDeputiesSummarizer(Summarizer):
    """
    Specialized summarizer for Chamber of Deputies session reports.

    This class implements the abstract methods to handle the Chamber of Deputies'
    specific data format for context (citations and results) and attendance
    (names and status) in comprehensive legislative analysis reports.
    """

    def get_context(self, session):
        """
        Format Chamber of Deputies session context information for report generation.

        Extracts and formats citations and results from Chamber of Deputies
        session context data into a structured format.

        Args:
            session: Dictionary containing Chamber of Deputies session data

        Returns:
            String containing formatted Chamber of Deputies context information
        """
        contexts = []
        for ctx in session["context"]:
            contexts.append(
                f"- Citación: {ctx.get('citation')}\n- Resultado: {ctx.get('result')}"
            )
        return "\n".join(contexts)

    def get_attendance(self, session):
        """
        Format Chamber of Deputies session attendance information for report generation.

        Extracts and formats attendee names and their attendance status
        from Chamber of Deputies session attendance records into a structured format.

        Args:
            session: Dictionary containing Chamber of Deputies session data

        Returns:
            String containing formatted Chamber of Deputies attendance information
        """
        attendees = []
        for att in session["attendance"]:
            attendees.append(f"- Nombre: {att.get('name')} Estado: {att.get('status')}")
        return "\n".join(attendees)


summarizers: dict[str, Summarizer] = {
    "Senado": SenateSummarizer(),
    "Cámara de Diputados": ChamberOfDeputiesSummarizer(),
}


def get_summarizer(data):
    """
    Factory function to get the appropriate summarizer for session data.

    Determines which chamber the session belongs to and returns the corresponding
    summarizer instance for generating comprehensive legislative analysis reports.

    Args:
        data: Dictionary containing session and commission information

    Returns:
        Summarizer instance appropriate for the session's chamber
    """
    commission = data["commission"]

    summarizer = summarizers[commission["chamber"]]

    return summarizer

from abc import ABC, abstractmethod
from seguimiento_parlamentario.processing.prompting import PromptModel
from babel.dates import format_datetime


class MindMapGenerator(PromptModel, ABC):
    """
    Abstract base class for generating structured mind maps from parliamentary session data.

    This class extends PromptModel to provide AI-powered mind map generation capabilities
    specifically tailored for parliamentary sessions, focusing on extracting and organizing
    key topics, discussions, and agreements in a hierarchical structure.
    """

    def __init__(self):
        """
        Initialize the mind map generator with parliamentary expertise.

        Sets up the base system message that defines the AI assistant's role as
        an expert in parliamentary topics specializing in mind map generation.
        """
        base_system_message = "Eres un asistente experto en temas parlamentarios que genera mapas mentales sobre sesiones del Congreso de Chile, explicando los temas tratados de forma estructurada."
        super().__init__(base_system_message)

    def build_prompt(self, data):
        """
        Construct the complete prompt for mind map generation.

        Builds a detailed prompt that includes session metadata, context, attendance,
        and transcription, along with specific instructions for creating structured
        JSON mind maps focused on relevant parliamentary topics and agreements.

        Args:
            data: Dictionary containing session and commission information

        Returns:
            String containing the complete prompt for AI processing
        """
        session = data["session"]
        commission = data["commission"]

        prompt = f"""
Genera un mapa mental a partir de la siguiente transcripción de una sesión de la {commission['name']} en {commission['chamber']} de Chile, realizada el día {format_datetime(session['start'], "EEEE d 'de' MMMM 'de' y", locale='es')}.

El mapa mental debe estar enfocado en los temas más relevantes discutidos durante la sesión, no incluyas discusiones suspendidas o aplazadas.

La raíz debe tener un título que sea representativo a lo discutido en la sesión. Cada rama que salga de la raíz debe abordar de forma general cada uno de los temas discutidos, y sus ramas hijas deben explicar a mayor detalle el tema discutido, explicando en que consiste y que acuerdos se obtuvieron, incluyendo datos específicos mencionados (como estadisticas, cifras relevantes, etc).

Estructura el resultado como un objeto JSON con nodos padre-hijo. Cada nodo debe tener:
- `name`: frase breve que explique la idea/concepto
- `children`: lista de nodos hijos (puede estar vacía)

Genera el JSON lo más limpio y estructurado posible.

Evita estructuras estándar como Resumen o Conclusión. Además, el mapa mental debe ir más allá de simples etiquetas de categorías como `Educación` o `Ejemplos`. Debe incluir detalles específicos, completa con hechos, no sólo el punto de partida básico. Si hay demasiado contenido para un mapa mental, también puedes acortar e ir más general, pero sólo si es realmente necesario. Intenta llegar a 2-3 niveles de profundidad. El mapa mental no debe ser abrumador. Evita construir ramas muy profundas con pocas bifurcaciones, en esos casos prefiere incluir la información en un solo nodo, separado por comas. Evita generar frases muy extensas, el contenido de una rama debe ser breve y conciso, entre 10 a 20 palabras de longitud, si debes explicar hazlo en una de las ramas hijas.

Aquí está el contexto, la lista de asistencia y la transcripción:

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


class SenateMindMapGenerator(MindMapGenerator):
    """
    Specialized mind map generator for Senate session data.

    This class implements the abstract methods to handle the Senate's specific
    data format for context (topics, aspects, agreements) and attendance
    (members and guests).
    """

    def get_context(self, session):
        """
        Format Senate session context information.

        Extracts and formats topics, aspects considered, and agreements
        from Senate session context data.

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
        Format Senate session attendance information.

        Extracts and formats member and guest attendance data from
        Senate session attendance records.

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


class ChamberOfDeputiesMindMapGenerator(MindMapGenerator):
    """
    Specialized mind map generator for Chamber of Deputies session data.

    This class implements the abstract methods to handle the Chamber of Deputies'
    specific data format for context (citations and results) and attendance
    (names and status).
    """

    def get_context(self, session):
        """
        Format Chamber of Deputies session context information.

        Extracts and formats citations and results from Chamber of Deputies
        session context data.

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
        Format Chamber of Deputies session attendance information.

        Extracts and formats attendee names and their attendance status
        from Chamber of Deputies session attendance records.

        Args:
            session: Dictionary containing Chamber of Deputies session data

        Returns:
            String containing formatted Chamber of Deputies attendance information
        """
        attendees = []
        for att in session["attendance"]:
            attendees.append(f"- Nombre: {att.get('name')} Estado: {att.get('status')}")
        return "\n".join(attendees)


mindmap_generators: dict[str, MindMapGenerator] = {
    "Senado": SenateMindMapGenerator(),
    "Cámara de Diputados": ChamberOfDeputiesMindMapGenerator(),
}


def get_mindmap(data):
    """
    Factory function to get the appropriate mind map generator for session data.

    Determines which chamber the session belongs to and returns the corresponding
    mind map generator instance.

    Args:
        data: Dictionary containing session and commission information

    Returns:
        MindMapGenerator instance appropriate for the session's chamber
    """
    commission = data["commission"]

    mindmap_generator = mindmap_generators[commission["chamber"]]

    return mindmap_generator

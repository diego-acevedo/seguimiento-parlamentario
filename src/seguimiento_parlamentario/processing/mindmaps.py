from abc import ABC, abstractmethod
from seguimiento_parlamentario.processing.prompting import PromptModel
from babel.dates import format_datetime

class MindMapGenerator(PromptModel, ABC):
  def __init__(self):
    base_system_message = "Eres un asistente experto en temas parlamentarios que genera mapas mentales sobre sesiones del Congreso de Chile, explicando los temas tratados de forma estructurada."
    super().__init__(base_system_message)

  def build_prompt(self, data):
    session = data["session"]
    commission = data["commission"]

    prompt = f"""
Genera un mapa mental a partir de la siguiente transcripción de una sesión de la {commission['name']} en {commission['chamber']} de Chile, realizada el día {format_datetime(session['start'], "EEEE d 'de' MMMM 'de' y", locale='es')}.

El mapa mental debe estar enfocado en los temas más relevantes discutidos durante la sesión, no incluyas discusiones suspendidas o aplazadas. La raíz debe tener un título que sea representativo a lo discutido en la sesión. Cada rama que salga de la raíz debe abordar de forma general cada uno de los temas discutidos, y sus subramas deben explicar a mayor detalle el tema discutido, explicando en que consiste y que acuerdos se obtuvieron, incluyendo datos específicos mencionados (como estadisticas, cifras relevantes, etc).

Estructura el resultado como un objeto JSON con nodos padre-hijo. Cada nodo debe tener:
- `name`: frase breve que explique la idea/concepto
- `children`: lista de nodos hijos (puede estar vacía)

Genera el JSON lo más limpio y estructurado posible.

Evita estructuras estándar como Resumen o Conclusión. ¡Es un mapa mental! Además, el mapa mental debe ir más allá de simples etiquetas de categorías como `Educación` o `Ejemplos`. Debe incluir detalles específicos, completa con hechos, no sólo el punto de partida básico. Si hay demasiado contenido para un mapa mental, también puedes acortar e ir más general, pero sólo si es realmente necesario. Intenta llegar a 2-3 niveles de profundidad. El mapa mental no debe ser abrumador. Evita construir ramas muy profundas con pocas bifurcaciones, en esos casos prefiere incluir la información en un solo nodo, separado por comas. Prefiere generar frases más largas por sobre ramas más profundas.

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
    ...

  @abstractmethod
  def get_attendance(self, session):
    ...

class SenateMindMapGenerator(MindMapGenerator):
  def get_context(self, session):
    contexts = []
    for ctx in session['context']:
      contexts.append(
        f"- Tema: {ctx.get('topic')}\n- Aspectos: {ctx.get('aspects')}\n- Acuerdos: {ctx.get('agreements')}"
      )
    return '\n'.join(contexts)

  def get_attendance(self, session):
    members = []
    guests = []
    for att in session['attendance'].get('members'):
      members.append(
          f"- Nombre: {att}"
      )
    for att in session['attendance'].get('guests'):
      guests.append(
          f"- {att}"
      )
    attendees = ["Miembros:", "\n".join(members), "Invitados:", "\n".join(guests)]
    return "\n".join(attendees)

class ChamberOfDeputiesMindMapGenerator(MindMapGenerator):
  def get_context(self, session):
    contexts = []
    for ctx in session['context']:
      contexts.append(
          f"- Citación: {ctx.get('citation')}\n- Resultado: {ctx.get('result')}"
      )
    return '\n'.join(contexts)

  def get_attendance(self, session):
    attendees = []
    for att in session['attendance']:
      attendees.append(
          f"- Nombre: {att.get('name')} Estado: {att.get('status')}"
      )
    return "\n".join(attendees)
  
mindmap_generators: dict[str, MindMapGenerator] = {
  "Senado": SenateMindMapGenerator(),
  "Cámara de Diputados": ChamberOfDeputiesMindMapGenerator(),
}

def get_mindmap(data):
  commission = data["commission"]

  mindmap_generator = mindmap_generators[commission["chamber"]]

  return mindmap_generator
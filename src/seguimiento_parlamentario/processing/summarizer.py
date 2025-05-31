from abc import ABC, abstractmethod
from seguimiento_parlamentario.processing.prompting import PromptModel
from babel.dates import format_datetime

class Summarizer(PromptModel, ABC):
  
  def __init__(self):
    base_system_message = "Eres un modelo experto en análisis legislativo. Tu tarea es leer y generar un reporte a partir de las transcripciones de sesiones del Congreso de Chile."
    super().__init__(base_system_message)
   
  def build_prompt(self, data):
    session = data["session"]
    commission = data["commission"]

    prompt = f"""
Genera un informe de la siguiente transcripción de una sesión de la {commission['name']} en {commission['chamber']} de Chile, realizada el día {format_datetime(session['start'], "EEEE d 'de' MMMM 'de' y", locale='es')}. El resumen debe estar organizado en las siguientes secciones:

### **Titular**: Crea un titular representativo de lo discutido en la sesión.
#### **Palabras claves**: Enumera las cinco palabras claves que mejor describan el contenido de la sesión. Deben ser relevantes y específicas a los problemas tratados en la sesión. Descarta palabras que puedan ser muy generales y que apliquen a la mayoría de las sesiones, como 'Legislación' o 'Congreso'.
#### **Temas principales tratados**: Enumera los temas más importantes discutidos durante la sesión, en formato de lista clara.
#### **Resumen de la sesión**: Redacta un texto en formato de noticia que informe sobre todos los puntos abordados en la sesión. Debe responder el 'Qué', 'Quién', 'Como', 'Donde', 'Cuando' y 'Por qué'. Se debe mencionar quienes intervinieron, cuales fueron sus intervenciones, y cual fue el descenlace de la discusión. Este texto debe tener una extensión de 500 palabras aproximadamente.
#### **Puntos de acuerdo**: Describe los puntos o temas en los que hubo consenso entre los participantes. Incluye los argumentos más relevantes que se entregaron a favor y explica por qué se logró el acuerdo, y quienes intervinieron.
#### **Puntos de desacuerdo**: Describe los puntos o temas que generaron discusión o desacuerdo. Explica las posturas contrapuestas, incluyendo los argumentos clave entregados por las distintas partes, quienes dieron estos argumentos, y por qué no se logró llegar a un consenso.
#### **Principales entidades**: Enumera personas, instituciones, eventos o lugares que fueron mencionadas en la sesión, y cual es su importancia para esta. Ignora entidades que sean muy generales y puedan aplicar a las demás sesiones, como 'Congreso', 'Gobierno de Chile' o los mismos parlamentarios.

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
    ...

  @abstractmethod
  def get_attendance(self, session):
    ...
  
class SenateSummarizer(Summarizer):
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

class ChamberOfDeputiesSummarizer(Summarizer):
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
  
summarizers: dict[str, Summarizer] = {
  "Senado": SenateSummarizer(),
  "Cámara de Diputados": ChamberOfDeputiesSummarizer(),
}

def get_summarizer(data):
  commission = data["commission"]

  summarizer = summarizers[commission["chamber"]]

  return summarizer
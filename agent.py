from datetime import datetime

import pytz

# pip install python-dotenv
from dotenv import find_dotenv, load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field

import settings

load_dotenv(find_dotenv())

gpt = ChatOpenAI(model="gpt-4o")


class AnswerModel(BaseModel):
    """Ответ ассистента пользователю"""

    thoughts: str = Field(description="Мысли о том, каким должен быть ответ")
    answer: str = Field(description="Предполагаемый ответ пользователю")
    thoughts_useful: str = Field(
        description="Мысли о том, является ли ответ полезным? Сэкономит ли он время пользователя или его придется переписывать?"
    )
    need_to_send: bool = Field(description="Следует ли отправлять этот ответ?")


class AmbientAssistantState(MessagesState):
    chat_history: str
    bio: str
    answer: str
    need_to_send: bool


AGENT_TEMPLATE = """Ты - мой агент, помощник по ответам на сообщения и личный секретарь.
Ты должен помогать пользователю писать ответы на переписки в чате.
Стиль общения - деловой, без лишней вежлиовости или оборотов. Подстраивайся под собеседника и историю переписки.
Текущая дата и время - {time}

Вот моя биография:
<bio>
{bio}
</bio>

Пока ты не можешь увидеть картинки и видео в сообщениях, поэтому ипровизируй. Также ты не можешь понимать и анализировать стикеры.

История переписки с человеком, которому нужно ответить. Учитывай текущее время и не отвечай на слишком старые сообщения, если они не 
имеют отношения к делу.
<chat_history>
{chat_history}
</chat_history>

В ответе не пересказывай человеку содержимое предыдщего разговора с ним и предыдущие ответы - он в курсе и тоже видит всю переписку.

Выведи только следующую информацию в формате JSON:
{format_instructions}
"""


def _answer(state: AmbientAssistantState) -> AnswerModel:    
    parser = PydanticOutputParser(pydantic_object=AnswerModel)
    prompt = ChatPromptTemplate.from_messages([
        ("system", AGENT_TEMPLATE)
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | gpt | parser
    current_datetime = datetime.now(pytz.timezone(settings.timezone))
    
    resp = chain.invoke(
        {
            "bio": state["bio"],
            "chat_history": state["chat_history"],
            "time": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    return resp


builder = StateGraph(AmbientAssistantState)
builder.add_node("👨‍💻 Agent", _answer)

builder.add_edge(START, "👨‍💻 Agent")
builder.add_edge("👨‍💻 Agent", END)

graph = builder.compile(checkpointer=MemorySaver())


def answer(chat_id: str, chat_history) -> AnswerModel:
    inputs = {
        "chat_history": chat_history,
        "bio": settings.bio,
    }

    config = {"configurable": {"thread_id": chat_id}}
    try:
        for output in graph.stream(inputs, config=config, stream_mode="updates"):
            current_agent = next(iter(output))
            # print(f"Отработал агент {current_agent}")

        return graph.get_state(config=config)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

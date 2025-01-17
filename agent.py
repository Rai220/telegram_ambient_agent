from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
import settings
from datetime import datetime
import pytz

# pip install python-dotenv
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

gpt = ChatOpenAI(model="gpt-4o")


class AmbientAssistantState(MessagesState):
    chat_history: str
    bio: str
    answer: str


def _write_answer(state: AmbientAssistantState):
    TEMPLATE = """Ты - мой агент, помощник по ответам на сообщения и личный секретарь.
Ты должен помогать пользователю писать ответы на переписки в чате.
Стиль общения - деловой, без лишней вежлиовости или оборотов. Подстраивайся под собеседника и историю переписки.
Текущая дата и время - {time}

Вот моя биография:
<bio>
{bio}
</bio>

Вот история переписки с человеком, которому нужно ответить. Учитывай текущее время и не отвечай на слишком старые сообщения, если они не 
имеют отношения к делу.

Пока ты не можешь увидеть картинки и видео в сообщениях, поэтому ипровизируй.

<chat_history>
{chat_history}
</chat_history>

Предложи вариант ответа, который нужно отправить человеку от моего имени, не пиши ничего больше.
"""
    chat_template = ChatPromptTemplate.from_messages(
        [
            ("system", TEMPLATE),
        ]
    )

    pipe = chat_template | gpt | StrOutputParser()
    current_datetime = datetime.now(pytz.timezone(settings.timezone))

    resp = pipe.invoke(
        {
            "bio": state["bio"],
            "chat_history": state["chat_history"],
            "time": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    return {"answer": resp}


builder = StateGraph(AmbientAssistantState)
builder.add_node("👨‍💻 Agent", _write_answer)

builder.add_edge(START, "👨‍💻 Agent")
builder.add_edge("👨‍💻 Agent", END)

graph = builder.compile(checkpointer=MemorySaver())


def answer(chat_history):
    inputs = {
        "chat_history": chat_history,
        "bio": settings.bio,
    }

    config = {"configurable": {"thread_id": "1"}}
    for output in graph.stream(inputs, config=config, stream_mode="updates"):
        current_agent = next(iter(output))
        # print(f"Отработал агент {current_agent}")

    return graph.get_state(config=config).values["answer"]

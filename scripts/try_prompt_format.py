from genio.core.llm import default_llm
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from rich import print

llm = default_llm()
prompt = ChatPromptTemplate.from_template("echo back to me: {foo['bar']}")

chain = prompt | llm | StrOutputParser()
response = chain.invoke({"foo": {"bar": "baz"}})
print(response)

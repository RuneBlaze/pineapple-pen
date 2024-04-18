from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOllama(model="mistral:7b-instruct-q5_0")

prompt = ChatPromptTemplate.from_template(
    "Give me a fake business profile of a business person specialized for children's shoes as if appearing in Vogue. Give me their name, age, and a very brief description in no more than four sentences including their artistic statement. Your writing will be a concept used for a light novel, but not using stereotypical Japanese words."
)

chain = prompt | llm | StrOutputParser()
business_person = chain.invoke({})
print(business_person)

prompt2 = ChatPromptTemplate.from_template(
    "Given this founder of the brand: \n```\n{description}\n```\n. Generate me a line name with the core line idea. The brand name should be chic. This brand should distinguish itself from its competitors. Your writing will be a concept used for a light novel, but no need to lean towards stereotypical Japanese concepts. Write several sentences."
)

chain = prompt2 | llm | StrOutputParser()

brand_name = chain.invoke({"description": business_person})
print(brand_name)

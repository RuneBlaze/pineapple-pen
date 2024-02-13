from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOllama(model="mistral:7b-instruct-q5_0")

prompt = ChatPromptTemplate.from_template(
    "Act as an excellent writer. Write me a short concept for a character for a light novel. The MC is a 110cm (very short) high school student who looks like five. The MC is male but looks like a loli. This character you write about is taller and much stronger (155cm, 10 year-old) than the MC but is much younger. She has like a big sister appearance to the MC despite being younger and she towers over the MC. She is large (bulky and tall) for her age, especially against the MC and likes to tease the size difference. Write her concept and her dynamics with the MC in roughly two paragraphs. Also, write a couple example light novel paragraphs (> 200 words) where the MC tries to wear his adorably little shoes and the character finds the little shoes cute and tries to compare their shoe sizes by directly placing her comparatively large feet next to the MC's."
)

# using LangChain Expressive Language chain syntax
# learn more about the LCEL on
# https://python.langchain.com/docs/expression_language/why
chain = prompt | llm | StrOutputParser()
res = chain.invoke({})
print(res)

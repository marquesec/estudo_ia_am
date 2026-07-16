from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal
import json

class Finding(BaseModel):
    vulnerability: str = Field(description="Vulnerability name")
    cwe_id: str = Field(description="CWE identifier, e.g. CWE-89")
    owasp_category: str = Field(description="OWASP Top 10 category")
    severity: Literal["Critical", "High", "Medium", "Low"]
    line_hint: str = Field(description="Where the issue occurs")
    remediation: str = Field(description="How to fix it")

class ScanResult(BaseModel):
    findings: list[Finding]

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
structured_llm = llm.with_structured_output(ScanResult)

prompt = ChatPromptTemplate.from_template(
    "You are an AppSec reviewer. Analyze this code for OWASP Top 10 issues.\n\nCODE:\n{code}"
)

chain = prompt | structured_llm

vulnerable = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)
"""

result = chain.invoke({"code": vulnerable})
print(json.dumps(result.model_dump(), indent=2))
from crewai import Agent, Task, Crew, LLM

llm = LLM(model="gemini/gemini-3.5-flash", temperature=0)

scanner = Agent(
    role="Security Scanner",
    goal="Find every potential vulnerability in the code — favor recall over precision",
    backstory="Aggressive SAST engine. You flag anything suspicious.",
    llm=llm,
    verbose=True
)

validator = Agent(
    role="False Positive Validator",
    goal="Determine which findings are actually exploitable in context",
    backstory=(
        "Skeptical AppSec architect with 17 years of experience. "
        "You know a legacy algorithm in a non-public, authorized-origin channel "
        "is not the same risk as one exposed to the internet. "
        "You hate noisy scanners because they make developers ignore security."
    ),
    llm=llm,
    verbose=True
)

scan_task = Task(
    description="Analyze this code and list ALL potential vulnerabilities:\n{code}",
    agent=scanner,
    expected_output="List of findings with CWE IDs and severity"
)

validate_task = Task(
    description=(
        "Review the scanner's findings. For each one, assess real exploitability "
        "in context. Discard false positives. Adjust severity to reflect actual risk."
    ),
    agent=validator,
    expected_output="Confirmed findings only, with justification for each decision"
)

crew = Crew(agents=[scanner, validator], tasks=[scan_task, validate_task])

vulnerable = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)

def hash_token(token):
    return hashlib.md5(token.encode()).hexdigest()
"""

print(crew.kickoff(inputs={"code": vulnerable}))
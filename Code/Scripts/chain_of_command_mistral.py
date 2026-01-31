import subprocess
from pathlib import Path
from textwrap import dedent

# -----------------------------------------
# 1. OLLAMA CALL FUNCTION
# -----------------------------------------
def run_ollama(model: str, prompt: str) -> str:
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


# -----------------------------------------
# 2. CHAIN-OF-COMMAND PROMPT BUILD
# -----------------------------------------
def build_chain_of_command_prompt(requirement: str) -> str:
    TEMPLATE = f"""
You are an expert software engineer and requirements analyst who converts
natural language requirements into UML State Machine Diagrams.

Follow THESE COMMANDS EXACTLY and IN ORDER.

COMMAND 1 — Extract all states.
List all major logical states that appear or are implied.

COMMAND 2 — Extract events/triggers.
List all actions, events, or conditions that cause transitions.

COMMAND 3 — Extract transitions.
For each event, identify:
- from state
- to state
- event/trigger name

COMMAND 4 — Infer missing transitions.
If the requirement implies a transition but does not explicitly state it,
infer it and mark it with (inferred).

COMMAND 5 — Validate.
Ensure that:
- There is exactly one initial state.
- All transitions refer to defined states.
- No orphan states.
- No unreachable states.
- Provide warnings if needed.

COMMAND 6 — Generate final PlantUML.
Use ONLY:
- @startuml / @enduml
- [*] for initial
- --> for transitions
DO NOT include any explanation outside the PlantUML block.

Example 1 — Door
Requirement:
A door can be closed, open, or locked...

PlantUML:
@startuml
[*] --> Closed
Closed --> Open : open
Open --> Closed : close
Closed --> Locked : lock
Locked --> Closed : unlock
@enduml

Example 2 — ATM
Requirement:
An ATM starts idle...

PlantUML:
@startuml
[*] --> Idle
Idle --> CardInserted : insert card
CardInserted --> PinEntry : card read
PinEntry --> TransactionMenu : PIN valid
PinEntry --> CardRetained : 3 invalid attempts
TransactionMenu --> PerformingTransaction : choose transaction
PerformingTransaction --> EjectingCard : transaction done
EjectingCard --> Idle : card ejected
CardRetained --> Idle : reset session
@enduml

NOW FOLLOW ALL SIX COMMANDS FOR THIS REQUIREMENT:

TARGET REQUIREMENT:
{requirement}

OUTPUT:
Return the answers for all commands AND the final PlantUML.
"""
    return dedent(TEMPLATE).strip()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = RESULTS_DIR / "text" / "chain_of_command"

# -----------------------------------------
# 3. YOUR SCENARIOS (fill in)
# -----------------------------------------
stories = {

       "accounts": """
    The Accounts class will be responsible for managing the financial aspects of the system.
    It will keep track of each product’s details to calculate the subtotal and maintain a record of sales history.
    Additionally, it will handle customers’ due payments and manage employee salaries and bonuses.
    Using the sales reports, the Accounts class will also generate and demonstrate profit or income
    for specific periods, ensuring accurate financial tracking and reporting within the system.
    """,

    "admin": """
    The Admin class will be responsible for managing the overall operations and ensuring system integrity. 
    After each recruitment, the admin adds new employees to the system and manages dealer information by 
    adding or changing dealers when necessary. When products are loaded, employee updates to the database 
    require admin approval to maintain data accuracy. The admin also receives SMS alerts if fire is detected 
    by the camera and can delete old or unnecessary CCTV footage. Additionally, the admin can adjust retail prices 
    based on market demand, view profit or loss data for specific time periods, place orders from dealers, and 
    review customer suggestions to improve service quality.
    """,

    "customers": """
    The Customers class will handle all customer-related activities within the system. It will calculate each 
    customer’s total orders and expenses based on their order details to maintain accurate purchase records. Customers
    will receive their order memos through SMS for convenience and transparency. Additionally, the system will 
    generate personalized recommendations for customers based on their purchasing patterns and preferences to
    enhance their shopping experience.
    """,

    "authentication": """
    The Authentication class will manage user access and security within the system. Both the owner and employees 
    can log in by providing their phone numbers and passwords. Employees have the ability to update their personal 
    information when necessary, ensuring their profiles remain accurate. Additionally, the system allows both the owner 
    and employees to reset their passwords securely in case they forget or wish to change them.
    """,

    "employees": """
    The Employee class will be responsible for handling day-to-day operational tasks within the system. Employees can add
    necessary information, update their profiles, and reset their passwords when needed. They will receive payments from 
    customers and ensure that new customer information is added to the system after each purchase. Employees will also be 
    responsible for updating the remaining stock levels to maintain inventory accuracy. In addition, they will receive their 
    salaries through the system and manage customer suggestions by storing them in the database for future service improvements.
    """,

    "inventory": """
    The Inventory class will manage and maintain detailed records of each product in the system. It will monitor product status 
    and notify dealers to exchange expired items when necessary. Based on various sales strategies, the owner can apply relevant 
    discounts to specific products to boost sales or clear stock. The inventory details will be regularly updated by either the 
    employee or the owner to ensure accurate and up-to-date product information.
    """,

    "logistic": """
    The Logistic class will handle the flow of products between the system and dealers. It will automatically send product requests 
    to the dealer when any item is about to run out of stock, ensuring timely restocking. Once the dealer sends the products, the 
    class will add the shipment details to the database for accurate tracking. Additionally, when a new dealer needs to be introduced, 
    their information will be recorded and maintained within the system to support smooth supply operations.
    """,

    "payment": """
    The Payment class will manage all payment-related activities within the system. Customers can make payments for both online and 
    offline orders using their preferred method—cash on delivery, digital payment, or on-spot transactions. After each successful payment, 
    a memo will be automatically generated to record the transaction details. Customers will receive notifications confirming their payment 
    status along with the memo for their reference and assurance.
    """,

    "order": """
    The Order class will be responsible for managing customer orders within the system. Employees will record all order details provided by customers 
    to ensure accurate processing. Once an order is finalized, the total expense will be automatically calculated based on the ordered items. 
    The complete order details will then be stored and linked to each registered customer’s account for future reference and tracking.
    """
  
}


# -----------------------------------------
# 4. MAIN LOOP + SAVE TO outputsChainOfCommand
# -----------------------------------------
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = "mistral"  # use mistral or llama3

    for name, req in stories.items():
        print(f"\n=== Running Chain-of-Command for {name} ===")

        prompt = build_chain_of_command_prompt(req)
        output = run_ollama(model, prompt)

        filepath = OUTPUT_DIR / f"{name}_{model}_chain_of_command.txt"
        filepath.write_text(output, encoding="utf-8")

        print(f"Saved → {filepath}")


if __name__ == "__main__":
    main()

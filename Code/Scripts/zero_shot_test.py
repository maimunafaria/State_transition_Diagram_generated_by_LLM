import subprocess


#
def run_ollama(model: str, prompt: str):
    command = f'ollama run {model} "{prompt}"' 
   
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')


        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
   
    except Exception as e:
        return f"An error occurred: {e}"


prompt = "Create a UML state transition diagram of the given exercise in PlantUml Format. " 
"Exercise: The Accounts class will be responsible for managing the financial aspects "
"of the system. It will keep track of each product’s details to calculate the subtotal "
"and maintain a record of sales history. Additionally, it will handle customers’ "
"due payments and manage employee salaries and bonuses. Using the sales reports, t"
"he Account class will also generate and demonstrate profit or income for specific "
"periods, ensuring accurate financial tracking and reporting within the system."


responseOfllama3 = run_ollama("llama3", prompt)
print("\n=== Llama3 Output ===\n")
print(responseOfllama3)
responseOfMistral = run_ollama("mistral", prompt)
print("\n=== Mistral Output ===\n")
print(responseOfMistral)
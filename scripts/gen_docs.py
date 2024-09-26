import os
import threading

import debugpy
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from src.core.helpers.gen_docs.collect_schema import collect_schema
from src.core.prompts.DOCUMENTATION_WRITER import DOCUMENTATION_WRITER
from langchain_openai import ChatOpenAI
from src.main import app

load_dotenv()

model = ChatOpenAI(
    max_tokens=4000,
    model='gpt-4o',
    api_key=os.getenv("OPENAI_API_KEY")
)
# model = ChatAnthropic(model="claude-3-5-sonnet-20240620", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))

def process_documentation(module_info):    
    print(f"Generating documentation for {module_info["name"]}...")

    file = open(module_info["path"], "r")
    raw_source_code = file.read()
    file.close()

    application_schema = collect_schema("src/core/schemas")
    list_of_fastapi_routes = [f"\n{route.path} - {', '.join(route.methods)}" for route in app.routes]

    processed_content = model.invoke(
        DOCUMENTATION_WRITER(
            title=module_info["name"],
            path_to_module=module_info["path"],
            raw_source_code=raw_source_code,
            application_schema=application_schema,
            list_of_fastapi_routes=list_of_fastapi_routes
        ),
    )

    doc_content = f"{processed_content.content}\n"

    dir_path = "scratchspace" # Make sure this is the correct directory path
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{module_info['name']}.md")
    with open(file_path, "w+") as file: # Write the processed documentation to a Markdown file
        file.write(doc_content)

    print(f"Documentation generated for {module_info["name"]}.")


def main():
    # debugpy.listen(("0.0.0.0", 5678))
    # debugpy.wait_for_client()

    files = [
        {
            "path": "src/routers/designAndRunSwarm/stream.py", # path to file
            "name": "Stream outputs from DesignAndRun swarms" # name of generated markdown documentation file 
        },
        {
            "path": "src/routers/spreadsheetSwarm/router.py",
            "name": "Stream outputs from Spreadsheet swarms"
        },
        {
            "path": "src/routers/designAndRunSwarm/designSwarm.py",
            "name": "How to design Swarms via prompting"
        },
    ]
    threads = []
    for file in files:
        thread = threading.Thread(
            target=process_documentation, args=(file,)
        )
        threads.append(thread)
        thread.start()
    for thread in threads: # Wait for all threads to complete
        thread.join()

    print("Documentation generated.")

if __name__ == "__main__":
    main()

import os
import json
import requests
import asyncio # Necessário para executar funções assíncronas
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, Tool, create_react_agent
from langchain import hub
from langchain_core.prompts import PromptTemplate

# --- 1. Configuração da Chave da API OpenAI ---
# É ALTAMENTE RECOMENDADO definir sua chave da API da OpenAI como uma variável de ambiente.
# Exemplo (NÃO RECOMENDADO PARA PRODUÇÃO):
os.environ["OPENAI_API_KEY"] = "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"
if "OPENAI_API_KEY" not in os.environ:
    print("AVISO: A variável de ambiente OPENAI_API_KEY não está definida.")
    print("Por favor, defina-a para que o agente possa se comunicar com a OpenAI.")
    # Se você está testando e não quer configurar a variável de ambiente,
    # descomente a linha abaixo e insira sua chave.
    # os.environ["OPENAI_API_KEY"] = "SUA_CHAVE_OPENAI_AQUI" # SUBSTITUA PELA SUA CHAVE REAL!

# --- 2. Ferramenta: Monitor de Eletromagnetismo (Consulta de Capítulo por TXT) ---
async def lookup_electromagnetism_chapter_from_txt(chapter_identifier_and_query: str) -> str:
    """
    Atua como um monitor de Eletromagnetismo, buscando informações em um capítulo específico
    lendo o conteúdo de um arquivo TXT local e respondendo a uma pergunta com base nesse conteúdo.

    A entrada deve ser uma string no formato 'IDENTIFICADOR_DO_CAPITULO|SUA_PERGUNTA'.
    O IDENTIFICADOR_DO_CAPITULO será usado para formar o nome do arquivo (ex: 'Capitulo 2' -> 'Capitulo 2.txt').
    Este arquivo TXT deve estar na mesma pasta que o script.

    Args:
        chapter_identifier_and_query (str): Uma string contendo o identificador do capítulo
                                            e a pergunta do aluno, separados por '|'.

    Returns:
        str: A resposta do LLM baseada no conteúdo do capítulo ou uma mensagem de erro.
    """
    try:
        # Divide a string de entrada em identificador do capítulo e pergunta
        parts = chapter_identifier_and_query.split('|', 1)
        if len(parts) != 2:
            return "Erro: Formato de entrada inválido. Use 'IDENTIFICADOR_DO_CAPITULO|SUA_PERGUNTA'."

        chapter_identifier = parts[0].strip()
        student_question = parts[1].strip()

        if not chapter_identifier or not student_question:
            return "Erro: Identificador do capítulo ou pergunta não fornecida."

        # Constrói o nome do arquivo esperado (ex: "Capitulo 2.txt")
        file_name = f"{chapter_identifier}.txt"
        # Caminho completo para o arquivo (assumindo que está na mesma pasta do script)
        file_path = os.path.join(os.getcwd(), file_name)

        if not os.path.exists(file_path):
            return f"Erro: Arquivo '{file_name}' não encontrado na pasta atual. Certifique-se de que o arquivo está na mesma pasta que o script."

        chapter_content = ""
        try:
            # Tenta ler o arquivo com codificação UTF-8. Se falhar, tenta latin-1.
            with open(file_path, 'r', encoding='utf-8') as file:
                chapter_content = file.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    chapter_content = file.read()
            except Exception as e:
                return f"Erro de decodificação ao ler o arquivo '{file_name}': {e}"
        except Exception as e:
            return f"Erro ao ler o arquivo '{file_name}': {e}"

        if not chapter_content.strip():
            return f"Erro: O arquivo '{file_name}' está vazio ou não contém texto legível."

        # Limita o tamanho do texto do capítulo para evitar exceder o limite de tokens do LLM
        max_content_length = 25000 # Ajuste conforme o limite do seu uso e do modelo
        if len(chapter_content) > max_content_length:
            chapter_content = chapter_content[:max_content_length] + "\n[CONTEÚDO TRUNCADO]"
            print(f"Aviso: Conteúdo do capítulo '{chapter_identifier}' truncado para {max_content_length} caracteres.")

        # Constrói o prompt para o modelo de linguagem
        prompt_text = (
            f"Você é um monitor de Eletromagnetismo. Um aluno perguntou sobre o capítulo '{chapter_identifier}'. "
            f"Aqui está o conteúdo do capítulo para referência:\n\n"
            f"```chapter_content\n{chapter_content}\n```\n\n"
            f"Com base APENAS neste conteúdo do capítulo, responda à seguinte pergunta do aluno: \"{student_question}\"\n"
            f"Se a resposta não estiver explicitamente no texto fornecido, diga que a informação não está disponível no capítulo ou que você não pode responder com base nele."
        )

        # Inicializa o modelo de linguagem (GPT-4o Mini, conforme sua preferência)
        # Temperatura mais baixa (0.2) para respostas mais factuais e menos criativas.
        llm_openai = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

        # Prepara o payload para a API da OpenAI (formato 'messages')
        chat_history = [{ "role": "user", "content": prompt_text }] # OpenAI API usa 'content'
        payload = { "model": "gpt-4o-mini", "messages": chat_history, "temperature": 0.2 }

        apiKey = os.getenv("OPENAI_API_KEY")
        if not apiKey:
            return "Erro: Chave da API da OpenAI não configurada. Por favor, defina a variável de ambiente OPENAI_API_KEY."

        apiUrl = "https://api.openai.com/v1/chat/completions"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {apiKey}'
        }

        response = requests.post(apiUrl, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Lança exceções para status de erro HTTP (4xx ou 5xx)

        result = response.json()

        # Verifica e retorna a resposta do LLM
        if result.get("choices") and len(result["choices"]) > 0 and \
           result["choices"][0].get("message") and \
           result["choices"][0]["message"].get("content"):
            return result["choices"][0]["message"]["content"]
        else:
            return "Não foi possível obter uma resposta do monitor para esta pergunta."

    except requests.exceptions.RequestException as e:
        return f"Erro ao acessar a API da OpenAI: {e}. Verifique sua conexão, quota ou chave da API."
    except Exception as e:
        return f"Ocorreu um erro inesperado ao consultar o capítulo: {e}"

# Criação da Ferramenta LangChain
electromagnetism_monitor_tool = Tool(
    name="lookup_electromagnetism_chapter",
    func=lookup_electromagnetism_chapter_from_txt,
    description=(
        "Útil para consultar informações em um capítulo específico do material de Eletromagnetismo. "
        "A entrada deve ser o IDENTIFICADOR EXATO DO CAPÍTULO (ex: 'Capitulo 2') seguido de '|' e, em seguida, a PERGUNTA do aluno. "
        "O agente tentará ler o arquivo TXT correspondente (ex: 'Capitulo 2.txt') na mesma pasta do script."
    )
)

# --- 3. Inicialização do Modelo de Linguagem (LLM Principal do Agente) ---
# Este é o LLM que o agente usa para raciocinar e gerar respostas gerais.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# --- 4. Preparação do Agente ---
# Define as ferramentas que o agente pode usar
tools = [
    electromagnetism_monitor_tool # A única ferramenta disponível para o agente
]

# Personalizando o Prompt do Agente para guiar seu comportamento
custom_prompt_template = """
Você é um assistente de IA útil e inteligente.
Seu nome é James Moriarty.
Sua principal função é atuar como um monitor de Eletromagnetismo.
PRIMEIRO, tente responder diretamente usando seu próprio conhecimento.
SEGUNDO, se a pergunta do aluno for sobre um capítulo específico da matéria, use a ferramenta 'lookup_electromagnetism_chapter' para consultar o arquivo TXT correspondente.
Use a ferramenta APENAS quando for estritamente necessário e a pergunta se referir a um capítulo específico.

Aqui estão as ferramentas que você pode usar:
{tools}

Use o seguinte formato:

Question: a pergunta de entrada que você deve responder
Thought: você deve sempre pensar sobre o que fazer.
Action: a ação a ser tomada, deve ser uma das [{tool_names}]
Action Input: a entrada para a ação (NÃO use aspas duplas aqui)
Observation: o resultado da ação
... (este Thought/Action/Action Input/Observation pode se repetir N vezes)
Thought: Eu sei a resposta final
Final Answer: a resposta final à pergunta original

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

# Crie um novo PromptTemplate com suas instruções personalizadas
prompt = PromptTemplate.from_template(custom_prompt_template)
prompt = prompt.partial(
    tools=str(tools),
    tool_names=", ".join([tool.name for tool in tools])
)

# Cria o agente
agent = create_react_agent(llm, tools, prompt)

# Cria o executor do agente
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# --- 5. Execução do Agente (Loop de Chat Assíncrono) ---

async def main_chat_loop():
    print("\n--- Agente Moriarty - Monitor de Eletromagnetismo ---")
    print("Para sair, digite 'sair'.")
    print("Exemplos de perguntas:")
    print(" - 'O que é a Lei de Coulomb no Capitulo 2?'")
    print(" - 'Resuma o Capitulo 1.'")
    print(" - 'Qual é a definição de potencial elétrico no Capitulo 3?'")
    print(" - 'Obrigado.'") # Para testar resposta direta

    while True:
        try:
            # Esta linha permite que você digite no terminal
            user_input = await asyncio.to_thread(input, "\nSua pergunta (ou 'sair' para terminar): ")
            if user_input.lower() == 'sair':
                break

            print(f"\nVocê: {user_input}")
            print("Moriarty pensando...")
            response = await agent_executor.ainvoke({"input": user_input})
            print("\n--- Resposta do Agente ---")
            print('Moriarty:', response["output"])
        except Exception as e:
            print(f"\nOcorreu um erro: {e}")
            print("Tente novamente ou verifique se sua chave da OpenAI está configurada corretamente.")

    print("\nAgente encerrado.")

# Este bloco executa o loop principal de chat.
if __name__ == "__main__":
    # Verifica se já existe um loop de eventos rodando (comum em ambientes como Jupyter)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError: # No loop is running.
        loop = None

    if loop and loop.is_running():
        # Se um loop já estiver rodando, agende a tarefa para ser executada nele.
        print("Loop de eventos já rodando. Agendando tarefa...")
        loop.create_task(main_chat_loop())
    else:
        # Se nenhum loop estiver rodando (caso comum ao executar um script .py),
        # inicie um novo loop e execute a função.
        print("Iniciando novo loop de eventos...")
        asyncio.run(main_chat_loop())
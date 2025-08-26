import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI
from dotenv import load_dotenv
from azure.search.documents.models import VectorizedQuery

# Load environment variables from a .env file
load_dotenv()

# --- Azure OpenAI Configuration for Embeddings ---
# This client is used to generate the vector embeddings from the text query.
client_embedding = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-02-01"
)

# --- Azure AI Search Configuration ---
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_KEY")
search_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

# Create a SearchClient instance to interact with the search index.
search_client = SearchClient(search_endpoint, search_index_name, AzureKeyCredential(search_key))

# --- Azure OpenAI Configuration for RAG Model ---
# This client is for the large language model that will generate the final response.
client_rag = AzureOpenAI(
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OAI_KEY"),
)
model_deployment = "gpt-35-turbo" # Replace with your deployment name if different

def generate_embeddings(text):
    """Generates a vector embedding for a given text."""
    try:
        response = client_embedding.embeddings.create(
            # NOTE: "text-embedding-ada-002" is a model ID, make sure it matches your deployment name.
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"An error occurred during embedding generation: {e}")
        return None

def retrieve_legal_info(query):
    """
    Searches the Azure AI Search index for relevant documents using a vector search.
    """
    query_vector = generate_embeddings(query)
    
    if not query_vector:
        return ""
    
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=3, # Changed back to 3 for better RAG context
        fields="text_vector"
    )

    context = []
    try:
        results = search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "chunk"]
        )
        
        for result in results:
            context.append(f"Title: {result.get('title', 'N/A')}\nChunk: {result.get('chunk', 'N/A')}")
            
    except Exception as e:
        print(f"An error occurred during search: {e}")
        return ""
        
    return " ".join(context)

def get_rag_response(query):
    """
    Retrieves context from the search index and generates a response using the LLM.
    """
    retrieved_context = retrieve_legal_info(query)

    # --- FIX: Truncate context to avoid token limit errors ---
    # The GPT-3.5-turbo model has a max context of 16385 tokens.
    # We will use a smaller value to be safe, as the system prompt and response also
    # consume tokens. A good, conservative limit is around 10,000 characters.
    MAX_CONTEXT_LENGTH = 10000 
    if len(retrieved_context) > MAX_CONTEXT_LENGTH:
        print("Warning: Retrieved context is too large, truncating...")
        retrieved_context = retrieved_context[:MAX_CONTEXT_LENGTH] + "..."
        
    # If no context is retrieved, inform the user.
    if not retrieved_context:
        return "I cannot find the answer in the provided documents.", ""

    try:
        response = client_rag.chat.completions.create(
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional legal Assistant. Answer questions based ONLY on the provided legal context. If the answer is not in the context, state 'I cannot find the answer in the provided documents.'",
                },
                {
                    "role": "user",
                    "content": f"Context: {retrieved_context}\n\nQuestion: {query}"
                }
            ],
            max_tokens=4096,
            temperature=1.0,
            top_p=1.0,
            model=model_deployment
        )
        return response.choices[0].message.content, retrieved_context
    except Exception as e:
        # Catch and handle API errors gracefully
        print(f"An error occurred during LLM completion: {e}")
        return f"An error occurred: {e}", ""

# The following lines are for testing the backend locally.
if __name__ == "__main__":
    test_query = "What is the title of the book?"
    rag_response, context = get_rag_response(test_query)
    print("--- RAG Response ---")
    print(rag_response)
    print("\n--- Retrieved Context ---")
    print(context)

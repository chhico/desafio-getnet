import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1/chat"

def test_agent(description, query):
    print(f"\n[Teste] {description}")
    print(f"Pergunta: {query}")
    try:
        response = requests.post(
            BASE_URL,
            json={"thread_id": "test_session", "message": query},
            headers={"X-Client-Channel": "test_cli"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Agente Usado: {data.get('agent_used')}")
            print(f"Resposta IA: {data.get('response')[:200]}...")
            return True
        else:
            print(f"ERRO ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"EXCEÇÃO: {str(e)}")
        return False

def run_all_tests():
    print("Iniciando bateria de testes do Agente do Zero (Versão Minimalista)...")
    
    # 1. Teste Support Agent & Tool (Status de Pedido)
    test_agent("Support & Status Pedido", "Qual o status do meu pedido PED-001?")
    
    # 2. Teste RAG Agent (Conhecimento Interno)
    test_agent("RAG & Knowledge Base", "Como funciona o processo de cancelamento de planos?")
    
    # 3. Teste Research Agent (Busca Web)
    test_agent("Research & Web Search", "Quem ganhou o Oscar de melhor filme em 2024?")
    
    # 4. Teste Tasks Agent (Tarefas)
    test_agent("Tasks Agent", "Crie uma tarefa para eu revisar o código hoje às 15h.")

if __name__ == "__main__":
    # Nota: Certifique-se de que o servidor está rodando (uvicorn backend.main:app)
    run_all_tests()

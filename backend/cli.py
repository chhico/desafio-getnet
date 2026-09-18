import sys
import os
from langchain_core.messages import HumanMessage, AIMessage

# Adiciona o diretório raiz ao path para permitir imports do pacote backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.graph import support_graph
from backend.core.config import settings

def main():
    print("=" * 60)
    print("  [CLI] Teste de Agentes - Invocação Direta ")
    print("  Digite 'sair' ou 'exit' para encerrar.")
    print("=" * 60)

    thread_id = "cli_session_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.AGENT_MAX_ITERATIONS,
    }

    while True:
        try:
            user_input = input("\n[Usuário]: ").strip()
            
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("\nEncerrando CLI. Até logo!")
                break
            
            if not user_input:
                continue

            print(f"[Sistema]: Processando com recursion_limit={settings.AGENT_MAX_ITERATIONS}...")

            # Invovação do grafo (mesma lógica do ConversationService)
            result = support_graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )

            # Extração da resposta
            all_msgs = result.get("messages", [])
            ai_msg = next((m.content for m in reversed(all_msgs) if isinstance(m, AIMessage)), 
                         "IA processou a mensagem mas não gerou resposta textual.")
            
            agent_used = result.get("next_agent", "unknown")

            print(f"\n[Agente ({agent_used})]: {ai_msg}")
            print("-" * 40)

        except KeyboardInterrupt:
            print("\nEncerrando CLI...")
            break
        except Exception as e:
            print(f"\n[ERRO]: {str(e)}")

if __name__ == "__main__":
    main()

import sys
import os
from langchain_core.messages import HumanMessage, AIMessage

# Adiciona o diretório raiz ao path para permitir imports do pacote backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.graph import support_graph
from backend.services.conversation_service import ConversationService

def main():
    print("=" * 60)
    print("  [CLI] Teste de Agentes - Invocação Direta ")
    print("  Digite 'sair' ou 'exit' para encerrar.")
    print("=" * 60)

    thread_id = "cli_session_001"

    while True:
        try:
            user_input = input("\n[Usuário]: ").strip()
            
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("\nEncerrando CLI. Até logo!")
                break
            
            if not user_input:
                continue

            response = ConversationService.process_message(
                graph=support_graph,
                user_id="cliente1988",
                message_content=user_input,
                thread_id=thread_id,
                channel="cli",
            )

            print(f"\n[Agente ({response.agent_used})]: {response.response}")
            if response.tools_used:
                print(f"[Ferramentas usadas]: {', '.join(response.tools_used)}")
            print("-" * 40)

        except KeyboardInterrupt:
            print("\nEncerrando CLI...")
            break
        except Exception as e:
            print(f"\n[ERRO]: {str(e)}")

if __name__ == "__main__":
    main()

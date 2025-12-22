import requests

# --- COLAR CHAVE AQUI ---
# Certifique-se que não há espaços antes do R ou depois do último caractere
API_KEY = "RGAPI-11d4cc33-0ca8-48c0-8619-f550d0fc50d9" 
# ------------------------

def testar_conexao():
    # Vamos testar um endpoint simples (Rotação de Campeões) que exige chave
    url = "https://br1.api.riotgames.com/lol/platform/v3/champion-rotations"
    
    headers = {
        "X-Riot-Token": API_KEY.strip() # .strip() remove espaços acidentais
    }

    print(f"--- DIAGNÓSTICO ---")
    print(f"Chave lida (primeiros 5 digitos): {API_KEY[:5]}...")
    print(f"Tamanho da chave: {len(API_KEY)} caracteres")
    
    try:
        response = requests.get(url, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCESSO! A chave está funcionando e o Python consegue conectar.")
            print("Dados recebidos:", list(response.json().keys()))
        elif response.status_code == 401:
            print("❌ ERRO 401: Não autorizado.")
            print("Causas prováveis:")
            print("1. A chave no código não é EXATAMENTE a do site.")
            print("2. Você salvou o arquivo antes de rodar?")
            print("3. A chave expirou (mas sua imagem diz que não).")
        elif response.status_code == 403:
            print("⚠️ ERRO 403: Proibido.")
            print("Sua chave é válida, mas não tem permissão para esse endpoint específico.")
        else:
            print(f"Erro inesperado: {response.text}")
            
    except Exception as e:
        print(f"Erro de conexão (Internet/DNS): {e}")

if __name__ == "__main__":
    testar_conexao()
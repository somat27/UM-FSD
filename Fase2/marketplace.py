import random
import socket
import json
import os
import time
import threading
import requests
 
Lock = threading.RLock()

conexoes = {}
produtos_comprados = {}
threads_heartbeat = {}
taxas_revenda = {}

taxa_padrao = 20.0

COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m' 

def obter_produtores():
    url = "http://193.136.11.170:5001/produtor"
    try:
        response = requests.get(url,timeout=2)
        return response.json() 
    except requests.exceptions.RequestException as e:
        return []

def obter_categorias(ip, porta):
    url = f"http://{ip}:{porta}/categorias"
    try:
        response = requests.get(url,timeout=2)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter categorias: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        return []
    
def obter_produtos_por_categoria(ip, porta, categoria):
    url = f"http://{ip}:{porta}/produtos?categoria={categoria}"
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        return []
    
def comprar_produto(ip, porta, produto, quantidade):
    url = f"http://{ip}:{porta}/comprar/{produto}/{quantidade}"
    try:
        response = requests.get(url)
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Compra realizada com sucesso: {produto} - Quantidade: {quantidade}")
    except requests.exceptions.RequestException as e:
        print(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {produto}: {e}")

def listar_subscricoes():
    if not produtos_comprados:
        print(f"{COR_ERRO}Erro: {COR_RESET}Você não tem nenhuma subscrição.")
        return
    print("--- Subscrições ---")
    for nome_produtor, dados_produtor in produtos_comprados.items():
        ip = dados_produtor["ip"]
        porta = dados_produtor["porta"]
        print(f"\nProdutor: {nome_produtor} (IP: {ip}, Porta: {porta})")
        for produto in dados_produtor["produtos"]:
            nome_produto = produto["nome"]
            quantidade = produto["quantidade"]
            preco_compra = produto["preco"]
            taxa_revenda = taxas_revenda.get(nome_produto, taxa_padrao)
            preco_venda = preco_compra + (preco_compra * taxa_revenda / 100)
            print(f" - {nome_produto} - Quantidade: {quantidade}\n\tPreço de Venda: {preco_venda:.2f}€ ( Preço de Compra: {preco_compra:.2f}€ | Taxa de Revenda: {taxa_revenda}%)")

def definir_taxa_revenda():
    if not produtos_comprados:
        print(f"{COR_ERRO}Erro: {COR_RESET}Nenhum produto foi comprado ainda.")
        return
    print("Produtos comprados disponíveis para revenda:")
    produtos_listados = []
    for nome_produtor, dados_produtor in produtos_comprados.items():
        for produto in dados_produtor["produtos"]:
            produtos_listados.append({
                "nome_produtor": nome_produtor,
                "ip": dados_produtor["ip"],
                "porta": dados_produtor["porta"],
                "nome_produto": produto["nome"],
                "quantidade": produto["quantidade"],
                "preco_compra": produto["preco"]
            })
    for i, produto in enumerate(produtos_listados, 1):
        nome_produto = produto["nome_produto"]
        nome_produtor = produto["nome_produtor"]
        quantidade = produto["quantidade"]
        taxa_atual = taxas_revenda.get(nome_produto, 0)
        preco_compra = produto["preco"]
        print(f"{i}. {nome_produto} - Quantidade: {quantidade}, Preço de Compra: {preco_compra}")
    try:
        escolha = int(input("\nEscolha o número do produto para definir a taxa de revenda: "))
        produto_escolhido = produtos_listados[escolha - 1]
        taxa = float(input(f"Digite a taxa de revenda para o produto {produto_escolhido['nome_produto']} (em %): "))
        
        if taxa < 0:
            print(f"{COR_ERRO}Erro: {COR_RESET}A taxa não pode ser negativa.")
            return
        taxas_revenda[produto_escolhido["nome_produto"]] = taxa
        print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Taxa de revenda de {taxa}% definida para o produto {produto_escolhido['nome_produto']}.")
    except (ValueError, IndexError):
        print(f"{COR_ERRO}Erro: {COR_RESET}Seleção inválida. Tente novamente.")

def conectar_ao_produtor(sock_antigo, ip, porta, nome_produtor):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, porta))
        conexoes[(ip, porta)] = (sock, nome_produtor)
        return sock
    except socket.error:
        return sock_antigo

def menu_marketplace():
    while True:
        print("--- Menu Marketplace ---")
        print("1. Lista de Subscrições")
        print("2. Comprar Produtos")
        print("3. Definir Taxa de Revenda")
        print("99. Sair")
        escolha = input("Escolha uma opção: ")
        if escolha == '1':
            listar_subscricoes()
        elif escolha == '2':
            marketplace()
        elif escolha == '3':
            definir_taxa_revenda()
        elif escolha == '99':
            print(f"{COR_SUCESSO}Sucesso: {COR_RESET}Saindo do Marketplace. Até logo!")
            break
        else:
            print(f"{COR_ERRO}Erro: {COR_RESET}Opção inválida. Tente novamente.")

def marketplace():
    produtores = obter_produtores()
    categorias_disponiveis = {}
    produtos_disponiveis = []
    global produtos_comprados
    for produtor in produtores:
        categorias = obter_categorias(produtor['ip'], produtor['porta'])
        if categorias:
            print(f"Produtor: {produtor['nome']}")
            for categoria in categorias:
                print(f" - {categoria}")
                if categoria not in categorias_disponiveis:
                    categorias_disponiveis[categoria] = []
                if produtor not in categorias_disponiveis[categoria]:
                    categorias_disponiveis[categoria].append(produtor)
    while True:
        categoria_escolhida = input("\nEscolha uma categoria: ")
        if categoria_escolhida in categorias_disponiveis:
            produtos_disponiveis = []
            for produtor in categorias_disponiveis[categoria_escolhida]:
                try:
                    produtos = obter_produtos_por_categoria(produtor['ip'], produtor['porta'], categoria_escolhida)
                    if produtos:
                        print(f"Produtor: {produtor['nome']}")
                        for index, produto in enumerate(produtos, start=1):
                            if all(key in produto for key in ['categoria', 'produto', 'preco', 'quantidade']):
                                produtos_disponiveis.append({
                                    "produtor": produtor,
                                    "produto": produto
                                })
                                print(f"{index} - {produto['produto']}, Preço: {produto['preco']}€, Quantidade: {produto['quantidade']}")
                            else:
                                print("Erro no formato dos dados do produto:", produto)
                except Exception as e:
                    print(f"Erro ao obter produtos do produtor {produtor['nome']} ({produtor['ip']}:{produtor['porta']}): {e}")
                    continue
            if produtos_disponiveis:
                break
            else:
                print(f"Não há produtos disponíveis na categoria '{categoria_escolhida}'. Por favor, escolha outra categoria.")
        else:
            print(f"A categoria '{categoria_escolhida}' não está disponível. Tente novamente.")
    while True:
        escolha = input("\nEscolha os números dos produtos que deseja comprar (separados por vírgula) ou 'sair' para encerrar: ")
        if escolha.lower() == 'sair':
            marketplace()
        numeros_escolhidos = []
        try:
            numeros_escolhidos = [int(num.strip()) for num in escolha.split(',')]
        except ValueError:
            print("Por favor, insira números válidos.")
            continue
        for num in numeros_escolhidos:
            produto_selecionado = produtos_disponiveis[num - 1]
            produto = produto_selecionado['produto']
            produtor = produto_selecionado['produtor']

            if produto['quantidade'] == 0:
                print(f"Produto {produto['produto']} não disponível.")
            elif 1 <= num <= len(produtos_disponiveis):
                while True:
                    try:
                        quantidade = int(input(f"Digite a quantidade para {produto['produto']} (disponível: {produto['quantidade']}): "))
                        if 1 <= quantidade <= produto['quantidade']:
                            ip = produtor['ip']
                            porta = produtor['porta']
                            nome_produtor = produtor['nome']
                            comprar_produto(ip, porta, produto['produto'], quantidade)
                            if nome_produtor not in produtos_comprados:
                                produtos_comprados[nome_produtor] = {
                                    "id_produtor": produtor.get("id", None),
                                    "ip": ip,
                                    "porta": porta,
                                    "produtos": []
                                }
                            produtos_comprados[nome_produtor]["produtos"].append({
                                "nome": produto['produto'],
                                "quantidade": quantidade,
                                "preco": produto['preco']
                            })
                            print(f"Produto {produto['produto']} comprado com sucesso.")
                            break
                        else:
                            print("Quantidade inválida. Tente novamente.")
                    except ValueError:
                        print("Por favor, insira um número válido.")
        break

def iniciar():
    marketplace()
    menu_marketplace()
    for sock, _ in conexoes.values():
        sock.close()
    print("Conexões fechadas.")

if __name__ == "__main__":
   iniciar()